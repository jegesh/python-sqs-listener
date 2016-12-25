AWS SQS Listener
----------------

This package takes care of the boilerplate involved in listening to an SQS
queue, as well as sending messages to a queue.

Installation
~~~~~~~~~~~~

``pip install pySqsListener``

Listening to a queue
~~~~~~~~~~~~~~~~~~~~

| Using the listener is very straightforward - just inherit from the
  ``SqsListener`` class and implement the ``handle_message()`` method.
  The queue will be created at runtime if it doesn't already exist.
  You can also specify an error queue to automatically push any errors to.

Here is a basic code sample:

**Standard Listener**

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

Running as a Daemon
~~~~~~~~~~~~~~~~~~~

| Typically, in a production environment, you'll want to listen to an SQS queue with a daemonized process.
  This can be achieved easily by inheriting from the package's ``Daemon`` class and overriding the ``run()`` method.
|
| The sample_daemon.py file in the source root folder provides a clear example for achieving this.  Using this example,
  you can run the listener as a daemon with the command ``python sample_daemon.py start``.  Similarly, the command
  ``python sample_daemon.py stop`` will stop the process.
|

Logging in daemon mode
######################  

| By default, the output and error messages of the listener are pushed to stdout and stderr, respectively.  This can
  be customized by using the optional parameters of the ``Daemon`` constructor.  For instance, the following
  example sets the standard output and error messages to be written to local logs, which are wiped clean every
  time the daemon is started.

::

    if __name__ == "__main__":
        daemon = MyDaemon('/var/run/sqs_daemon.pid', True, 'sqs_out.log', 'sqs_err.log')
        ...

Sending messages
~~~~~~~~~~~~~~~~

| In order to send a message, instantiate an ``SqsLauncher`` with the name of the queue.  By default an exception will
  be raised if the queue doesn't exist, but it can be created automatically if the ``create_queue`` parameter is
  set to true.  In such a case, there's also an option to set the newly created queue's ``VisibilityTimeout`` via the
  third parameter.
|
| After instantiation, use the ``launch_message()`` method to send the message.  The message body should be a ``dict``,
  and additional kwargs can be specified as stated in the [SQS docs](http://boto3.readthedocs.io/en/latest/reference/services/sqs.html#SQS.Client.send_message).
  The method returns the response from SQS.

**Launcher Example**

::

    from sqs_launcher import SqsLauncher

    launcher = SqsLauncher('my-queue')
    response = launcher.launch_message({'param1': 'hello', 'param2': 'world'})

Important Notes
~~~~~~~~~~~~~~~

-  The environment variable ``AWS_ACCOUNT_ID`` must be set, in addition
   to the environment having valid AWS credentials (via environment variables or a credentials file)
-  For both the main queue and the error queue, if the queue doesn’t
   exist (in the specified region), it will be created at runtime.
-  The error queue receives only two values in the message body: ``exception_type`` and ``error_message``. Both are of type ``str``

Contributing
~~~~~~~~~~~~

Fork the repo and make a pull request.