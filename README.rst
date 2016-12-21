AWS SQS Listener
----------------

This package takes care of the boilerplate involved in creating an SQS
listening agent.

Installation
~~~~~~~~~~~~

``pip install``

Usage
~~~~~

| Using the package is very straightforward - just inherit from the
  ``SqsListener`` class and implement the
| ``handle_message()`` method.

Here is a basic code sample:

| **Standard Listener**

::

    from sqs_listener import SqsListener
    class MyListener(SqsListener):
        def handle_message(self, body, attributes, messages_attributes):
            run_my_function(body['param1'], body['param2']

    listener = MyListener('my-message-queue', 'my-error-queue')
    listener.listen()

**Error Listener**

::

    from sqs_listener import SqsListener
    class MyErrorListener(SqsListener):
        def handle_message(self, body, attributes, messages_attributes):
            save_to_log(body['exception_type'], body['error_message']

    error_listener = MyErrorListener('my-error-queue')
    error_listener.listen()

**Notes**

-  The environment variable ``AWS_ACCOUNT_ID`` must be set, in addition
   to the environment having valid AWS credentials (via environment variables or a credentials file)
-  For both the main queue and the error queue, if the queue doesn’t
   exist (in the specified region), it will be created at runtime.
-  The error queue receives only two values in the message body: ``exception_type`` and ``error_message``. Both are of type ``str``

Upcoming Features
~~~~~~~~~~~~~~~~~

Create an issue with a suggestion for a feature, and I’ll see what I can
do!