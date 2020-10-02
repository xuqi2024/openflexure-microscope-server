Threads and Locks
=================

Introduction
------------

Some actions in your extension may perform tasks that take a long time (compared to the expected response time of a web request). For example, if you were to implement a timelapse feature, this inherently runs over a long time.

This introduces a couple of problems. Firstly, a request that triggers a long function will, by default, block the Python interpreter for the duration of the function. This usually causes the connection to timeout, and the response will never be revieved.

Similarly, if your functionality takes a long time, it may be possible for other requests to interfere with your function. For example, in our hypothetical timelapse extension, while the timelapse is running, another user could open a connection and start moving the stage around, ruining the timelapse.

We get around these issues by making use of action threads, and component locks.

Action threads
--------------

Action threads are introduced to manage long-running functions in a way that does not block HTTP requests. Any API Action will automatically run as a background thread.

Internally, the :class:`labthings.LabThing` object stores a list of all requested actions, and their states. This state stores the running status of the action (if itis idle, running, error, or success), information about the start and end times, a unique ID, and, upon completion, the return value of the long-running function. 

By using threads, a function can be started in the background, and it's return value fetched at a later time once it has reported success. If a long-running action is started by some client, it should note the ID returned in the action state JSON, and use this to periodically check on the status of that particular action. 

API routes have been created to allow checking the state of all actions (GET ``/actions``), a particular action by ID (GET ``/actions/<action_id>``), and stopping or removing individual actions (DELETE ``/actions/<action_id>``).

All actions will return a serialized representation of the action state when your POST request returns. If the action completes within a default timeout period (usually 1 second) then the completed action representation will be returned. If the action is still running after this timeout period, the "in-progress" action representation will be returned. The final output value can then be retrieved at a later time.

Most users will not need to create instances of this class. Instead, they will be created automatically when a function is started by an API Action view.

An example of a long running task may look like:

.. code-block:: python

    ...
    from labthings import ActionView

    class SlowAPI(ActionView):
        def post(self):
            # Return the task object.
            return long_running_function(function_argument_1, function_argument_2)

After some time, once the task has completed, it could be retreived using:

.. code-block:: python

    ...
    from labthings import current_labthing

    def get_result(action_id):
        matching_action = current_labthing().actions.get(task_id)
        return matching_action.state

or by making GET requests to the ``http://microscope.local/api/v2/tasks/<task_id>`` view.


Accessing the current action instance
+++++++++++++++++++++++++++++++++++++

Every time a user requests your action, a new :class:`labthings.actions.ActionThread` instance is created to hold the state of your action. This object holds return values, errors, action progress and status, and handles action cancellation.

In some cases, your action function will need to access the currently running :class:`labthings.actions.ActionThread` instance. The :func:`labthings.current_action` function will return the currently running :class:`labthings.actions.ActionThread` instance if it's called from within an ``ActonThread``, and will return ``None`` if running outside of an `ActionThread`.


Handling action cancellation
++++++++++++++++++++++++++++

Users always have the option to stop an action while it's running. Your action function has the option to support an elegant cancellation by watching for cancellation requests on the running :class:`labthings.actions.ActionThread` instance.

The ``labthings.current_action().stopped`` attribute will return ``True`` if the Action has been requested to stop, and ``False`` otherwise. If your action runs a loop, this can be checked at each iteration, and used to return early if the action has been stopped.

If a stop request is sent and your action does not return within a timeout (by default 5 seconds), then the thread will be forcefully terminated. This is to ensure that actions can be stopped even if they have become stuck, or would otherwise take an unexpected amount of time. However, every effort should be made to handle action cancellation elegantly from within the action.

An example of elegant action cancellation is included in the example later on this page.

The ``ActionView.default_stop_timeout`` class attribute can be used to increase or descrease the forced cancellation timeout. Developers should carefully consider how long their action should take to elegantly stop, and avoid abusing this timeout override to simply prevent forceful cancelltion.


Updating action progress
++++++++++++++++++++++++

Some applications such as OpenFlexure eV are able to display progress bars showing the progress of an action thread. Implementing progress updates in your extension is made easy with the :py:meth:`labthings.update_action_progress` function. This function takes a single argument, which is the action progress as an integer percent (0 - 100).

If your long running function was started within a background thread, this function will update the state of the corresponding action thread object. If your function is called outside of a long-running task (e.g. by another extension, directly), then this function will silently do nothing.

An example of task progress is included in the example later on this page.


Component Locks
---------------

Locks have been implemented to solve a distinct issue, most obvious when considering long-running actions. During a long action such as a tile-scan or autofocus, it is absolutely necesarry to block any completing interaction with the microscope hardware. For example, even if the stage is not actively moving (for example during a capture phase within a tile scan), another user should not be able to move the microscope, interrupting the action. Thread locks act to prevent this.

The camera and stage both contain an instance of :py:class:`labthings.lock.StrictLock`, named ``lock``. Built-in functions such as capture and move will always acquire this lock for the duration of the function. This ensures that, for example, simultaneous attemps to move do not occur.

More importantly, however, threads can hold on to these locks for longer periods of time, blocking any other calls to the hardware.

Locks are acquired using context managers, i.e. ``with component.lock: ...``


Complete example
----------------

Implementing both action threads and locks in a new timelapse extension may look like:

.. literalinclude:: ./example_extension/06_tasks_locks.py

Notice that even though we never use the stage here, our ``timelapse`` function still acquires the stage lock. This means that during the timelapse, no other user is able to move the stage, or take separate captures. Control of the microscope is handed exclusively to the thread that obtains the lock, which in this case is the thread spawned when handling the POST request.
