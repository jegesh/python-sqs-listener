"""Tests for the credential / AWS_ACCOUNT_ID gate.

Regression coverage for issue #62 (support of shared-credentials-file):
credentials resolved from a shared credentials file (or any other provider)
must be accepted even when ``AWS_ACCOUNT_ID`` is not set.
"""

import boto3
import pytest
from moto import mock_aws

from sqs_launcher import SqsLauncher
from sqs_listener import SqsListener


class _Listener(SqsListener):
    def handle_message(self, body, attributes, messages_attributes):
        pass


@mock_aws
def test_listener_accepts_shared_credentials_file(monkeypatch):
    """A non-role credential method (e.g. shared-credentials-file) must work."""
    real_get_credentials = boto3.Session.get_credentials

    def fake_get_credentials(self):
        creds = real_get_credentials(self)
        if creds is not None:
            creds.method = "shared-credentials-file"
        return creds

    monkeypatch.setattr(boto3.Session, "get_credentials", fake_get_credentials)

    # Should not raise EnvironmentError just because the method isn't a role.
    listener = _Listener("some-queue", region_name="us-east-1")
    assert listener._queue_url is not None


@mock_aws
def test_launcher_accepts_shared_credentials_file(monkeypatch):
    real_get_credentials = boto3.Session.get_credentials

    def fake_get_credentials(self):
        creds = real_get_credentials(self)
        if creds is not None:
            creds.method = "shared-credentials-file"
        return creds

    monkeypatch.setattr(boto3.Session, "get_credentials", fake_get_credentials)

    launcher = SqsLauncher("some-queue", create_queue=True)
    assert launcher._queue_url is not None


def test_listener_raises_when_no_credentials_and_no_account_id(monkeypatch):
    """The safety net stays: no credentials AND no account id is still an error."""
    monkeypatch.setattr(boto3.Session, "get_credentials", lambda self: None)

    with pytest.raises(EnvironmentError):
        _Listener("some-queue", region_name="us-east-1")


def test_launcher_raises_when_no_credentials_and_no_account_id(monkeypatch):
    monkeypatch.setattr(boto3.Session, "get_credentials", lambda self: None)

    with pytest.raises(EnvironmentError):
        SqsLauncher("some-queue", create_queue=True)
