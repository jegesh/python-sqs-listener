"""
script for running sqs listener

Created December 21st, 2016
@author: Yaakov Gesher
@version: 0.2.3
@license: Apache
"""

# ================
# start imports
# ================

import boto3
import boto3.session
import json
import time
import logging
import os
import sys
from sqs_launcher import SqsLauncher
from abc import ABCMeta, abstractmethod

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

        if all([aws_access_key, aws_secret_key]):
            boto3_session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
            )
        else:
            if (not os.environ.get('AWS_ACCOUNT_ID', None) and
                    not ('iam-role' == boto3.Session().get_credentials().method)):
                raise EnvironmentError('Environment variable `AWS_ACCOUNT_ID` not set and no role found.')
        self._queue = None         # The SQS Queue resource
        self._queue_name = queue
        self._poll_interval = kwargs.get("interval", 60)
        self._queue_visibility_timeout = kwargs.get('visibility_timeout', '600')
        self._error_queue_name = kwargs.get('error_queue', None)
        self._error_queue_visibility_timeout = kwargs.get('error_visibility_timeout', '600')
        self._queue_url = kwargs.get('queue_url', None)
        self._message_attribute_names = kwargs.get('message_attribute_names', [])
        self._attribute_names = kwargs.get('attribute_names', [])
        self._force_delete = kwargs.get('force_delete', False)
        self._endpoint_name = kwargs.get('endpoint_name', None)
        self._wait_time = kwargs.get('wait_time', 0)
        self._max_number_of_messages = kwargs.get('max_number_of_messages', 1)

        # must come last
        if boto3_session:
            self._session = boto3_session
        else:
            self._session = boto3.session.Session()
        self._region_name = kwargs.get('region_name', self._session.region_name)
        self._resource = self._initialize_resource()

    def _initialize_resource(self):
        # new session for each instantiation
        ssl = True
        if self._region_name == 'elasticmq':
            ssl = False

        sqs = self._session.resource('sqs', region_name=self._region_name, endpoint_url=self._endpoint_name, use_ssl=ssl)
        queues = sqs.queues.filter(QueueNamePrefix=self._queue_name)
        main_queue_exists = False
        error_queue_exists = False
        for q in queues:
            qname = q.url.split('/')[-1]
            if qname == self._queue_name:
                main_queue_exists = True
            if self._error_queue_name and qname == self._error_queue_name:
                error_queue_exists = True

        # create queue if necessary.
        # creation is idempotent, no harm in calling on a queue if it already exists.
        if self._queue_url is None:
            if not main_queue_exists:
                sqs_logger.warning("main queue not found, creating now")
                queue_attributes = {
                    'VisibilityTimeout': self._queue_visibility_timeout,  # 10 minutes
                }
                # is this a fifo queue?
                if self._queue_name.endswith(".fifo"):
                    queue_attributes["FifoQueue"] = "true"
                q = sqs.create_queue(
                    QueueName=self._queue_name,
                    Attributes=queue_attributes,
                )
                self._queue_url = q.url

        if self._error_queue_name and not error_queue_exists:
            sqs_logger.warning("error queue not found, creating now")
            q = sqs.create_queue(
                QueueName=self._error_queue_name,
                Attributes={
                    'VisibilityTimeout': self._queue_visibility_timeout,  # 10 minutes
                },
            )

        if self._queue_url is None:
            qs = sqs.get_queue_by_name(
                QueueName=self._queue_name,
                QueueOwnerAWSAccountId=os.environ.get('AWS_ACCOUNT_ID', None),
            )
            self._queue_url = qs.url
        self._queue = sqs.Queue(self._queue_url)
        return sqs

    def _start_listening(self):
        # TODO consider incorporating output processing from here:
        # https://github.com/debrouwere/sqs-antenna/blob/master/antenna/__init__.py
        while True:
            # calling with `WaitTimeSecconds` of zero show the same behavior as
            # not specifiying a wait time, ie: short polling
            messages = self._queue.receive_message(
                AttributeNames=self._attribute_names,
                MessageAttributeNames=self._message_attribute_names,
                WaitTimeSeconds=self._wait_time,
                MaxNumberOfMessages=self._max_number_of_messages,
            )
            if not messages:
                time.sleep(self._poll_interval)
                continue
            sqs_logger.debug(messages)
            sqs_logger.info("{} messages received".format(len(messages['Messages'])))
            for m in messages:
                receipt_handle = m.receipt_handle
                m_body = m.body
                message_attribs = m.message_attributes
                attribs = m.attributes
                # catch problems with malformed JSON, usually a result of someone writing poor JSON directly in the AWS console
                try:
                    params_dict = json.loads(m_body)
                except:
                    sqs_logger.warning("Unable to parse message - JSON is not formatted properly")
                    continue
                try:
                    if self._force_delete:
                        m.delete()
                        self.handle_message(params_dict, message_attribs, attribs)
                    else:
                        self.handle_message(params_dict, message_attribs, attribs)
                        m.delete()
                except Exception as ex:
                    # need exception logtype to log stack trace
                    sqs_logger.exception(ex)
                    if self._error_queue_name:
                        exc_type, exc_obj, exc_tb = sys.exc_info()

                        sqs_logger.info( "Pushing exception to error queue")
                        error_launcher = SqsLauncher(queue=self._error_queue_name, create_queue=True)
                        error_launcher.launch_message(
                            {
                                'exception_type': str(exc_type),
                                'error_message': str(ex.args)
                            }
                        )

    def listen(self):
        sqs_logger.info( "Listening to queue " + self._queue_name)
        if self._error_queue_name:
            sqs_logger.info( "Using error queue " + self._error_queue_name)

        self._start_listening()

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
