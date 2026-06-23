"""When a handler raises, the failing message must be forwarded to the error
queue that was resolved during initialization."""

import json

import boto3
from moto import mock_aws

from sqs_listener import SqsListener


class _Stop(Exception):
    """Sentinel used to break out of the otherwise-infinite poll loop."""


@mock_aws
def test_handler_exception_is_pushed_to_error_queue():
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="work-queue")
    error_url = sqs.create_queue(QueueName="dead-letters")["QueueUrl"]

    class _Listener(SqsListener):
        def handle_message(self, body, attributes, messages_attributes):
            raise ValueError("boom")

    listener = _Listener(
        "work-queue", error_queue="dead-letters", region_name="us-east-1"
    )

    # First poll yields one message; the second poll aborts the loop so the
    # test doesn't spin forever.
    calls = {"n": 0}
    messages = [
        {"Messages": [{"ReceiptHandle": "rh", "Body": json.dumps({"hi": 1})}]},
    ]

    def fake_receive(**kwargs):
        if calls["n"] < len(messages):
            msg = messages[calls["n"]]
            calls["n"] += 1
            return msg
        raise _Stop()

    listener._client.receive_message = fake_receive

    try:
        listener._start_listening()
    except _Stop:
        pass

    received = sqs.receive_message(QueueUrl=error_url, WaitTimeSeconds=0)
    assert "Messages" in received
    payload = json.loads(received["Messages"][0]["Body"])
    assert "boom" in payload["error_message"]
    assert "ValueError" in payload["exception_type"]
