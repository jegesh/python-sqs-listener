"""
Created December 21st, 2016
@author: Yaakov Gesher
@version: 0.9.0
@license: Apache
"""

# ================
# start imports
# ================

import json
import logging
import os
import sys
import time
from abc import ABCMeta, abstractmethod

import boto3
import boto3.session
from botocore.exceptions import SSOTokenLoadError

from sqs_launcher import SqsLauncher

# ================
# start class
# ================

sqs_logger = logging.getLogger('sqs_listener')


class SqsListener(object):
    __metaclass__ = ABCMeta

    def __init__(self, queue, **kwargs):
        """
        :param queue: (str) name of queue to listen to
        :param kwargs: options for fine tuning. see below
        """
        aws_access_key = kwargs.get('aws_access_key', '')
        aws_secret_key = kwargs.get('aws_secret_key', '')

        boto3_session = None
        if len(aws_access_key) != 0 and len(aws_secret_key) != 0:
            boto3_session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
        else:
            boto3_session = None
            # Accept credentials from any provider boto3 can resolve (env vars,
            # shared credentials file, config file, container/instance roles,
            # SSO, assumed roles, ...). AWS_ACCOUNT_ID is only needed as a
            # fallback when no credentials are discoverable. See issue #62.
            if not os.environ.get('AWS_ACCOUNT_ID', None) and boto3.Session().get_credentials() is None:
                raise EnvironmentError(
                    'No AWS credentials found and environment variable `AWS_ACCOUNT_ID` is not set.'
                )

        self._queue_name = queue
        self._poll_interval = kwargs.get("interval", 60)
        self._queue_visibility_timeout = kwargs.get('visibility_timeout', '600')
        self._error_queue_name = kwargs.get('error_queue', None)
        self._error_queue_visibility_timeout = kwargs.get('error_visibility_timeout', '600')
        self._queue_url = kwargs.get('queue_url', None)
        self._error_queue_url = None
        self._message_attribute_names = kwargs.get('message_attribute_names', [])
        self._attribute_names = kwargs.get('attribute_names', [])
        self._force_delete = kwargs.get('force_delete', False)
        self._endpoint_name = kwargs.get('endpoint_name', None)
        self._wait_time = kwargs.get('wait_time', 0)
        self._max_number_of_messages = kwargs.get('max_number_of_messages', 1)
        self._deserializer = kwargs.get("deserializer", json.loads)

        # must come last
        if boto3_session:
            self._session = boto3_session
        else:
            self._session = boto3.session.Session()
        self._region_name = kwargs.get('region_name', self._session.region_name)
        self._client = self._initialize_client()

    def _initialize_client(self):
        # new session for each instantiation
        ssl = True
        if self._region_name == 'elasticmq':
            ssl = False

        sqs = self._session.client('sqs', region_name=self._region_name, endpoint_url=self._endpoint_name, use_ssl=ssl)

        # Resolve each queue by its exact name rather than by a shared name
        # prefix. The old prefix-based lookup misidentified error queues that
        # don't share the main queue's prefix (and CloudFormation-generated
        # names), causing spurious queue creation and QueueNameExists errors.
        # See issues #43 and #61.
        if self._queue_url is None:
            self._queue_url = self._get_or_create_queue_url(
                sqs, self._queue_name, self._queue_visibility_timeout
            )

        if self._error_queue_name:
            self._error_queue_url = self._get_or_create_queue_url(
                sqs, self._error_queue_name, self._error_queue_visibility_timeout
            )

        return sqs

    def _get_or_create_queue_url(self, sqs, queue_name, visibility_timeout):
        """Return the URL of ``queue_name``, creating the queue only if absent.

        Creation is skipped when the queue already exists, so pre-created
        queues (including ones whose names don't share a common prefix) are
        used as-is instead of triggering a QueueNameExists error.
        """
        try:
            account_id = os.environ.get('AWS_ACCOUNT_ID', None)
            if account_id:
                response = sqs.get_queue_url(QueueName=queue_name, QueueOwnerAWSAccountId=account_id)
            else:
                response = sqs.get_queue_url(QueueName=queue_name)
            return response['QueueUrl']
        except sqs.exceptions.QueueDoesNotExist:
            sqs_logger.warning("queue %s not found, creating now", queue_name)
        except SSOTokenLoadError:
            raise EnvironmentError('Error loading SSO Token. Reauthenticate via aws sso login.')

        attributes = {'VisibilityTimeout': visibility_timeout}
        # FIFO queues must be created with the FifoQueue attribute; it must be
        # omitted for standard queues.
        if queue_name.endswith(".fifo"):
            attributes['FifoQueue'] = "true"
        return sqs.create_queue(QueueName=queue_name, Attributes=attributes)['QueueUrl']

    def _start_listening(self):
        # TODO consider incorporating output processing from here: https://github.com/debrouwere/sqs-antenna/blob/master/antenna/__init__.py
        while True:
            # calling with WaitTimeSecconds of zero show the same behavior as
            # not specifiying a wait time, ie: short polling
            messages = self._client.receive_message(
                QueueUrl=self._queue_url,
                MessageAttributeNames=self._message_attribute_names,
                AttributeNames=self._attribute_names,
                WaitTimeSeconds=self._wait_time,
                MaxNumberOfMessages=self._max_number_of_messages
            )
            if 'Messages' in messages:

                sqs_logger.debug(messages)
                sqs_logger.info("{} messages received".format(len(messages['Messages'])))
                for m in messages['Messages']:
                    receipt_handle = m['ReceiptHandle']
                    m_body = m['Body']
                    message_attribs = None
                    attribs = None

                    try:
                        deserialized = self._deserializer(m_body)
                    except:
                        sqs_logger.exception("Unable to parse message")
                        continue

                    if 'MessageAttributes' in m:
                        message_attribs = m['MessageAttributes']
                    if 'Attributes' in m:
                        attribs = m['Attributes']
                    try:
                        if self._force_delete:
                            self._client.delete_message(
                                QueueUrl=self._queue_url,
                                ReceiptHandle=receipt_handle
                            )
                            self.handle_message(deserialized, message_attribs, attribs)
                        else:
                            self.handle_message(deserialized, message_attribs, attribs)
                            self._client.delete_message(
                                QueueUrl=self._queue_url,
                                ReceiptHandle=receipt_handle
                            )
                    except Exception as ex:
                        sqs_logger.exception(ex)
                        if self._error_queue_name:
                            exc_type, exc_obj, exc_tb = sys.exc_info()

                            sqs_logger.info("Pushing exception to error queue")
                            # The error queue was already resolved/created during
                            # initialization, so reuse its URL instead of looking
                            # it up again on every failure.
                            error_launcher = SqsLauncher(queue_url=self._error_queue_url)
                            error_launcher.launch_message(
                                {
                                    'exception_type': str(exc_type),
                                    'error_message': str(ex.args)
                                }
                            )

            else:
                time.sleep(self._poll_interval)

    def listen(self):
        sqs_logger.info("Listening to queue " + self._queue_name)
        if self._error_queue_name:
            sqs_logger.info("Using error queue " + self._error_queue_name)

        self._start_listening()

    def _prepare_logger(self):
        logger = logging.getLogger('eg_daemon')
        logger.setLevel(logging.INFO)

        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)

        formatstr = '[%(asctime)s - %(name)s - %(levelname)s]  %(message)s'
        formatter = logging.Formatter(formatstr)

        sh.setFormatter(formatter)
        logger.addHandler(sh)

    @abstractmethod
    def handle_message(self, body, attributes, messages_attributes):
        """
        Implement this method to do something with the SQS message contents
        :param body: dict
        :param attributes: dict
        :param messages_attributes: dict
        :return:
        """
        return
