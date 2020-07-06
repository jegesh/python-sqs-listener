AWS SQS Listener
----------------

.. image:: https://img.shields.io/pypi/v/pySqsListener.svg?style=popout
   :alt: PyPI
   :target: https://github.com/jegesh/python-sqs-listener
.. image:: https://img.shields.io/pypi/pyversions/pySqsListener.svg?style=popout
   :alt: PyPI - Python Version
   :target: https://pypi.org/project/pySqsListener/




This package takes care of the boilerplate involved in listening to an SQS
queue, as well as sending messages to a queue.  Works with python 2.7 & 3.6+.

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

.. code:: python

    from sqs_listener import SqsListener

    class MyListener(SqsListener):
        def handle_message(self, body, attributes, messages_attributes):
            run_my_function(body['param1'], body['param2'])

    listener = MyListener('my-message-queue', error_queue='my-error-queue', region_name='us-east-1')
    listener.listen()

**Error Listener**

.. code:: python

    from sqs_listener import SqsListener
    class MyErrorListener(SqsListener):
        def handle_message(self, body, attributes, messages_attributes):
            save_to_log(body['exception_type'], body['error_message']

    error_listener = MyErrorListener('my-error-queue')
    error_listener.listen()


| The options available as ``kwargs`` are as follows:

- error_queue (str) - name of queue to push errors.
- force_delete (boolean) - delete the message received from the queue, whether or not the handler function is successful.  By default the message is deleted only if the handler function returns with no exceptions
- interval (int) - number of seconds in between polls. Set to 60 by default
- visibility_timeout (str) - Number of seconds the message will be invisible ('in flight') after being read.  After this time interval it reappear in the queue if it wasn't deleted in the meantime.  Set to '600' (10 minutes) by default
- error_visibility_timeout (str) - Same as previous argument, for the error queue.  Applicable only if the ``error_queue`` argument is set, and the queue doesn't already exist.
- wait_time (int) - number of seconds to wait for a message to arrive (for long polling). Set to 0 by default to provide short polling.
- max_number_of_messages (int) - Max number of messages to receive from the queue. Set to 1 by default, max is 10
- message_attribute_names (list) - message attributes by which to filter messages
- attribute_names (list) - attributes by which to filter messages (see boto docs for difference between these two)
- region_name (str) - AWS region name (defaults to ``us-east-1``)
- queue_url (str) - overrides ``queue`` parameter. Mostly useful for getting around `this bug <https://github.com/aws/aws-cli/issues/1715>`_ in the boto library


Running as a Daemon
~~~~~~~~~~~~~~~~~~~

| Typically, in a production environment, you'll want to listen to an SQS queue with a daemonized process.
  The simplest way to do this is by running the listener in a detached process.  On a typical Linux distribution it might look   like this:
|
  ``nohup python my_listener.py > listener.log &``
|  And saving the resulting process id for later (for stopping the listener via the ``kill`` command).
|
  A more complete implementation can be achieved easily by inheriting from the package's ``Daemon`` class and overriding the ``run()`` method.
|
| The sample_daemon.py file in the source root folder provides a clear example for achieving this.  Using this example,
  you can run the listener as a daemon with the command ``python sample_daemon.py start``.  Similarly, the command
  ``python sample_daemon.py stop`` will stop the process.  You'll most likely need to run the start script using ``sudo``.
|

Logging
~~~~~~~

| The listener and launcher instances push all their messages to a ``logger`` instance, called 'sqs_listener'.
  In order to view the messages, the logger needs to be redirected to ``stdout`` or to a log file.
|
| For instance:

.. code:: python

    logger = logging.getLogger('sqs_listener')
    logger.setLevel(logging.INFO)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)

    formatstr = '[%(asctime)s - %(name)s - %(levelname)s]  %(message)s'
    formatter = logging.Formatter(formatstr)

    sh.setFormatter(formatter)
    logger.addHandler(sh)

|
| Or to a log file:

.. code:: python

    logger = logging.getLogger('sqs_listener')
    logger.setLevel(logging.INFO)

    sh = logging.FileHandler('mylog.log')
    sh.setLevel(logging.INFO)

    formatstr = '[%(asctime)s - %(name)s - %(levelname)s]  %(message)s'
    formatter = logging.Formatter(formatstr)

    sh.setFormatter(formatter)
    logger.addHandler(sh)

Sending messages
~~~~~~~~~~~~~~~~

| In order to send a message, instantiate an ``SqsLauncher`` with the name of the queue.  By default an exception will
  be raised if the queue doesn't exist, but it can be created automatically if the ``create_queue`` parameter is
  set to true.  In such a case, there's also an option to set the newly created queue's ``VisibilityTimeout`` via the
  third parameter.
|
| After instantiation, use the ``launch_message()`` method to send the message.  The message body should be a ``dict``,
  and additional kwargs can be specified as stated in the `SQS docs
  <http://boto3.readthedocs.io/en/latest/reference/services/sqs.html#SQS.Client.send_message>`_.
  The method returns the response from SQS.

**Launcher Example**

.. code:: python

    from sqs_launcher import SqsLauncher

    launcher = SqsLauncher('my-queue')
    response = launcher.launch_message({'param1': 'hello', 'param2': 'world'})

Important Notes
~~~~~~~~~~~~~~~

-  The environment variable ``AWS_ACCOUNT_ID`` must be set, in addition
   to the environment having valid AWS credentials (via environment variables
   or a credentials file) or if running in an aws ec2 instance a role attached
   with the required permissions.
-  For both the main queue and the error queue, if the queue doesn’t
   exist (in the specified region), it will be created at runtime.
-  The error queue receives only two values in the message body: ``exception_type`` and ``error_message``. Both are of type ``str``
-  If the function that the listener executes involves connecting to a database, you should explicitly close the connection at the end of the function.  Otherwise, you're likely to get an error like this: ``OperationalError(2006, 'MySQL server has gone away')``
-  Either the queue name or the queue url should be provided. When both are provided the queue url is used and the queue name is ignored.

Contributing
~~~~~~~~~~~~

Fork the repo and make a pull request.
