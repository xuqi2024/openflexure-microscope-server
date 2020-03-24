Tasks and Locks
===============

Introduction
------------

Some actions in your extension may perform tasks that take a long time (compared to the expected response time of a web request). For example, if you were to implement a timelapse feature, this inherently runs over a long time.

This introduces a couple of problems. Firstly, a request that triggers a long function will, by default, block the Python interpreter for the duration of the function. This usually causes the connection to timeout, and the response will never be revieved.

Similarly, if your functionality takes a long time, it may be possible for other requests to interfere with your function. For example, in our hypothetical timelapse extension, while the timelapse is running, another user could open a connection and start moving the stage around, ruining the timelapse.

We get around these issues by making use of background tasks, and component locks.

Background tasks
----------------

Tasks are introduced to manage long-running functions in a way that does not block HTTP requests. Any function can be offloaded to a background task, and this is done through the :py:meth:`labthings.tasks.taskify` function, by calling ``taskify(<long_running_function>)(*args, **kwargs)``. 

Internally, the ``tasks`` submodule stores a list of all requested tasks, and their states. This state stores the running status of the task (if itis idle, running, error, or success), information about the start and end times, a unique task ID, and, upon completion, the return value of the long-running function. 

By using tasks, a function can be started in the background, and it's return value fetched at a later time once it has reported success. If a long-running task is started by some client, it should note the ID returned in the task state JSON, and use this to periodically check on the status of that particular task. 

API routes have been created to allow checking the state of all tasks (GET ``/tasks``), a particular task by ID (GET ``/tasks/<task_id>``), and terminating or removing individual tasks (DELETE ``/tasks/<task_id>``).

A special ``@marshal_task`` decorator provides shorthand for automatically returning a serialized representation of the task, when your POST request returns.

An example of a long running task may look like:

.. code-block:: python

    ...
    from labthings.tasks import taskify
    from labthings.server.decorators import marshal_task

    class SlowAPI(View):
        @marshal_task
        def post(self):
            # Run the long-running function as a task
            task = taskify(long_running_function)(function_argument_1, function_argument_2)
            # Return the task object. Let @marshal_task handle serialization
            return task

After some time, once the task has completed, it could be retreived using:

.. code-block:: python

    ...
    from labthings import tasks

    def get_result(task_id):
        matching_task = tasks.dict.get(task_id)
        return matching_task.state

or by making GET requests to the ``http://microscope.local/api/v2/tasks/<task_id>`` view.


Updating task progress
++++++++++++++++++++++

Some applications such as OpenFlexure eV are able to display progress bars showing the progress of a background task. Implementing progress updates in your extension is made easy with the :py:meth:`labthings.tasks.update_task_progress` function. This function takes a single argument, which is the task progress as an integer percent (0 - 100).

If your long running function was started within a background task, this function will update the state of the corresponding task object. If your function is called outside of a long-running task (e.g. by another extension, directly), then this function will silently do nothing.

An example of task progress is included in the example later on this page.


Component Locks
---------------

Locks have been implemented to solve a distinct issue, most obvious when considering long-running tasks. During a long task such as a tile-scan or autofocus, it is absolutely necesarry to block any completing interaction with the microscope hardware. For example, even if the stage is not actively moving (for example during a capture phase within a tile scan), another user should not be able to move the microscope, interrupting the task. Thread locks act to prevent this.

The camera and stage both contain an instance of :py:class:`labthings.lock.StrictLock`, named ``lock``. Built-in functions such as capture and move will always acquire this lock for the duration of the function. This ensures that, for example, simultaneous attemps to move do not occur.

More importantly, however, tasks can hold on to these locks for longer periods of time, blocking any other calls to the hardware.

Locks are acquired using context managers, i.e. ``with component.lock: ...``


Complete example
----------------

Implementing both tasks and locks in a new timelapse extension may look like:

.. literalinclude:: ./example_extension/06_tasks_locks.py

Notice that even though we never use the stage here, our ``timelapse`` function still acquires the stage lock. This means that during the timelapse, no other user is able to move the stage, or take separate captures. Control of the microscope is handed exclusively to the thread that obtains the lock, which in this case is the thread spawned when handling the POST request.
