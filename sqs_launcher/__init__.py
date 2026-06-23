"""
class for running sqs message launcher

Created December 22nd, 2016
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

import boto3
import boto3.session

# ================
# start class
# ================

sqs_logger = logging.getLogger('sqs_listener')


class SqsLauncher(object):

    def __init__(self, queue=None, queue_url=None, create_queue=False, visibility_timeout='600', serializer=json.dumps):
        """
        :param queue: (str) name of queue to listen to
        :param queue_url: (str) url of queue to listen to
        :param create_queue (boolean) determines whether to create the queue if it doesn't exist.  If False, an
                                    Exception will be raised if the queue doesn't already exist
        :param visibility_timeout: (str) Relevant to queue creation.  Indicates the number of seconds for which the SQS will hide the message.
                                    Typically this should reflect the maximum amount of time your handler method will take
                                    to finish execution. See http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
                                    for more information
        """
        if not any([queue, queue_url]):
            raise ValueError('Either `queue` or `queue_url` should be provided.')
        
        # Accept credentials from any provider boto3 can resolve (env vars,
        # shared credentials file, config file, container/instance roles, SSO,
        # assumed roles, ...). AWS_ACCOUNT_ID is only needed as a fallback when
        # no credentials are discoverable. See issue #62.
        if not os.environ.get('AWS_ACCOUNT_ID', None) and boto3.Session().get_credentials() is None:
            raise EnvironmentError(
                'No AWS credentials found and environment variable `AWS_ACCOUNT_ID` is not set.'
            )
        
        # new session for each instantiation
        self._session = boto3.session.Session()
        self._client = self._session.client('sqs')

        self._queue_name = queue
        self._queue_url = queue_url
        self._serializer = serializer

        if not queue_url:
            # Resolve the queue by its exact name instead of a name prefix, so a
            # queue is not confused with another whose name it is a prefix of.
            # See issues #43 and #61.
            try:
                self._queue_url = self._client.get_queue_url(QueueName=self._queue_name)['QueueUrl']
            except self._client.exceptions.QueueDoesNotExist:
                if create_queue:
                    q = self._client.create_queue(
                        QueueName=self._queue_name,
                        Attributes={
                            'VisibilityTimeout': visibility_timeout  # 10 minutes
                        }
                    )
                    self._queue_url = q['QueueUrl']
                else:
                    raise ValueError('No queue found with name ' + self._queue_name)
        else:
            self._queue_name = self._get_queue_name_from_url(queue_url)

    def launch_message(self, message, **kwargs):
        """
        sends a message to the queue specified in the constructor
        :param message: (dict)
        :param kwargs: additional optional keyword arguments (DelaySeconds, MessageAttributes, MessageDeduplicationId, or MessageGroupId)
                        See http://boto3.readthedocs.io/en/latest/reference/services/sqs.html#SQS.Client.send_message for more information
        :return: (dict) the message response from SQS
        """
        sqs_logger.info("Sending message to queue " + self._queue_name)
        return self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=self._serializer(message),
            **kwargs
        )

    def _get_queue_name_from_url(self, url):
        return url.split('/')[-1]
