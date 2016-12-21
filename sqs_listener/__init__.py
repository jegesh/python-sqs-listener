"""
script for running sqs listener

Created December 21st, 2016
@author: Yaakov Gesher
@version: 0.1.0
@license: Creative Commons (attribution)
"""

# ================
# start imports
# ================

import boto3
import json
import time
import os
from abc import ABCMeta, abstractmethod

# ================
# start class
# ================


class SqsListener(object):
    __metaclass__ = ABCMeta

    def __init__(self, queue, interval=60, visibility_timeout='600'):
        if not os.environ.get('AWS_ACCOUNT_ID', None):
            raise EnvironmentError('Environment variable `AWS_ACCOUNT_ID` not set')
        self._queue_name = queue
        self._poll_interval = interval
        self._queue_visibility_timeout = visibility_timeout

    def listen(self):
        sqs = boto3.client('sqs')

        # create queue if necessary
        qs = sqs.get_queue_url(QueueName=self._queue_name, QueueOwnerAWSAccountId=os.environ.get('AWS_ACCOUNT_ID', None))
        if 'QueueUrl' not in qs:
            q = sqs.create_queue(
                QueueName=self._queue_name,
                Attributes={
                    'VisibilityTimeout': self._queue_visibility_timeout  # 10 minutes
                }
            )
            qurl = q['QueueUrl']
        else:
            qurl = qs['QueueUrl']

        # listen to queue
        while True:
            messages = sqs.receive_message(
                QueueUrl=qurl
            )
            if 'Messages' in messages:
                for m in messages['Messages']:
                    receipt_handle = m['ReceiptHandle']
                    m_body = m['Body']
                    attribs = None
                    params_dict = json.loads(m_body)
                    if 'Attributes' in m:
                        attribs = m['Attributes']
                    try:
                        self.handle_message(m_body, attribs)
                        sqs.delete_message(
                            QueueUrl=qurl,
                            ReceiptHandle=receipt_handle
                        )
                    except Exception, ex:
                        # TODO send the exception somewhere
                        print repr(ex)

            else:
                time.sleep(self._poll_interval)

    @abstractmethod
    def handle_message(self, body, attributes):
        return
