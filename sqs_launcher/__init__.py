"""
class for running sqs message launcher

Created December 22nd, 2016
@author: Yaakov Gesher
@version: 0.1.0
@license: Apache
"""

# ================
# start imports
# ================

import boto3
import json
import os

# ================
# start class
# ================


class SqsLauncher(object):

    def __init__(self, queue, create_queue=False, visibility_timeout='600'):
        """
        :param queue: (str) name of queue to listen to
        :param create_queue (boolean) determines whether to create the queue if it doesn't exist.  If False, an
                                    Exception will be raised if the queue doesn't already exist
        :param visibility_timeout: (str) Relevant to queue creation.  Indicates the number of seconds for which the SQS will hide the message.
                                    Typically this should reflect the maximum amount of time your handler method will take
                                    to finish execution. See http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
                                    for more information
        """
        if not os.environ.get('AWS_ACCOUNT_ID', None):
            raise EnvironmentError('Environment variable `AWS_ACCOUNT_ID` not set')
        self._client = boto3.client('sqs')
        self._queue_name = queue
        queue_data = self._client.get_queue_url(QueueName=queue,
                     QueueOwnerAWSAccountId=os.environ.get('AWS_ACCOUNT_ID', None))
        if 'QueueUrl' in queue_data:
            self._queue_url = queue_data['QueueUrl']
        else:
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

    def launch_message(self, message, **kwargs):
        """
        sends a message to the queue specified in the constructor
        :param message: (dict)
        :param kwargs: additional optional keyword arguments (DelaySeconds, MessageAttributes, MessageDeduplicationId, or MessageGroupId)
                        See http://boto3.readthedocs.io/en/latest/reference/services/sqs.html#SQS.Client.send_message for more information
        :return: (dict) the message response from SQS
        """
        print "Sending message to queue " + self._queue_name
        if not kwargs:
            return self._client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps(message)
            )
        return self._client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps(message),
                **kwargs
            )

