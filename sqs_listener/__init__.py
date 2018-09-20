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

import json
import logging
import os
import sys
import time
from abc import ABCMeta, abstractmethod

import boto3
import boto3.session

from sqs_launcher import SqsLauncher

# ================
# start class
# ================

sqs_logger = logging.getLogger('sqs_listener')


class SqsListener(object):
    __metaclass__ = ABCMeta

    def __init__(self, queue=None, queue_url=None, **kwargs):
        """
        :param queue: (str) name of queue to listen to
        :param queue_url: (str) url of queue to listen to
        :param kwargs: error_queue=None, interval=60, visibility_timeout='600', error_visibility_timeout='600', force_delete=False
        """
        if not queue and not queue_url:
            raise ValueError('Either `queue` or `queue_url` should be provided.')
        if (not os.environ.get('AWS_ACCOUNT_ID', None) and
                not (boto3.Session().get_credentials().method in ['iam-role', 'assume-role'])):
            raise EnvironmentError('Environment variable `AWS_ACCOUNT_ID` not set and no role found.')
        self._queue_name = queue
        self._queue_url = queue_url
        self._poll_interval = kwargs.get("interval", 60)
        self._queue_visibility_timeout = kwargs.get('visibility_timeout', '600')
        self._error_queue_name = kwargs.get('error_queue', None)
        self._error_queue_url = kwargs.get('error_queue_url', None)
        self._error_queue_visibility_timeout = kwargs.get( 'error_visibility_timeout', '600')
        self._message_attribute_names = kwargs.get('message_attribute_names', [])
        self._attribute_names = kwargs.get('attribute_names', [])
        self._force_delete = kwargs.get('force_delete', False)
        self._region_name = kwargs.get('region_name', None)
        self._wait_time = kwargs.get('wait_time', 0)
        self._max_number_of_messages = kwargs.get('max_number_of_messages', 1)
        # must come last
        self._client = self._initialize_client()

    def _initialize_client(self):
        # sqs = boto3.client('sqs', region_name=self._region_name)

        # new session for each instantiation
        self._session = boto3.session.Session()
        sqs = self._session.client('sqs', region_name=self._region_name)

        if not self._queue_url:
            queues = sqs.list_queues(QueueNamePrefix=self._queue_name)
            main_queue_exists = False
            if 'QueueUrls' in queues:
                for q in queues['QueueUrls']:
                    qname = self._get_queue_name_from_url(q)
                    if qname == self._queue_name:
                        main_queue_exists = True

            # create queue if necessary.
            # creation is idempotent, no harm in calling on a queue if it already exists.
            if not main_queue_exists:
                sqs_logger.warning("main queue not found, creating now")

                # is this a fifo queue?
                if self._queue_name.endswith(".fifo"):
                    fifoQueue = "true"
                    q = sqs.create_queue(
                        QueueName=self._queue_name,
                        Attributes={
                            'VisibilityTimeout': self._queue_visibility_timeout,  # 10 minutes
                            'FifoQueue': fifoQueue
                        }
                    )
                else:
                    # need to avoid FifoQueue property for normal non-fifo queues
                    q = sqs.create_queue(
                        QueueName=self._queue_name,
                        Attributes={
                            'VisibilityTimeout': self._queue_visibility_timeout,  # 10 minutes
                        }
                    )
                self._queue_url = q['QueueUrl']
            else:
                if os.environ.get('AWS_ACCOUNT_ID', None):
                    qs = sqs.get_queue_url(QueueName=self._queue_name,
                                           QueueOwnerAWSAccountId=os.environ.get('AWS_ACCOUNT_ID', None))
                else:
                    qs = sqs.get_queue_url(QueueName=self._queue_name)
                self._queue_url = qs['QueueUrl']
        else:
            self._queue_name = self._get_queue_name_from_url(self._queue_url)
        return sqs

    def _start_listening(self):
        # TODO consider incorporating output processing from here: https://github.com/debrouwere/sqs-antenna/blob/master/antenna/__init__.py
        while True:
            # calling with WaitTimeSeconds of zero show the same behavior as
            # not specifiying a wait time, ie: short polling
            messages = self._client.receive_message(
                QueueUrl=self._queue_url,
                MessageAttributeNames=self._message_attribute_names,
                AttributeNames=self._attribute_names,
                WaitTimeSeconds=self._wait_time,
                MaxNumberOfMessages=self._max_number_of_messages
            )
            if 'Messages' in messages:
                sqs_logger.info(str(len(messages['Messages'])) + " messages received")
                for m in messages['Messages']:
                    receipt_handle = m['ReceiptHandle']
                    m_body = m['Body']
                    message_attribs = None
                    attribs = None

                    # catch problems with malformed JSON, usually a result of someone writing poor JSON directly in the AWS console
                    try:
                        params_dict = json.loads(m_body)
                    except:
                        sqs_logger.warning("Unable to parse message - JSON is not formatted properly")
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
                            self.handle_message(params_dict, message_attribs, attribs)
                        else:
                            self.handle_message(params_dict, message_attribs, attribs)
                            self._client.delete_message(
                                QueueUrl=self._queue_url,
                                ReceiptHandle=receipt_handle
                            )
                    except Exception as ex:
                        # need exception logtype to log stack trace
                        sqs_logger.exception(ex)
                        if self._error_queue_url or self._error_queue_name:
                            exc_type, exc_obj, exc_tb = sys.exc_info()

                            sqs_logger.info("Pushing exception to error queue")
                            error_launcher = SqsLauncher(self._error_queue_name, self._error_queue_url, True)
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

    def _get_queue_name_from_url(self, url):
        return url.split('/')[-1]

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
