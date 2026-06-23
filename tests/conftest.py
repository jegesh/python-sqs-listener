"""Shared pytest fixtures for the SQS listener/launcher test-suite."""

import os

import pytest


@pytest.fixture(autouse=True)
def aws_environment(monkeypatch):
    """Provide a clean, predictable AWS environment for every test.

    - A default region so boto3 clients can be created under moto.
    - Dummy static credentials so ``get_credentials()`` resolves.
    - ``AWS_ACCOUNT_ID`` removed so the credential gate is actually exercised
      (several issues are specifically about behaviour when it is unset).
    """
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.delenv("AWS_ACCOUNT_ID", raising=False)
