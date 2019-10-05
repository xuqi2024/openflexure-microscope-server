Accessing the microscope
========================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Introduction
------------
All instances of :py:class:`openflexure_microscope.api.v1.views.MicroscopeViewPlugin` must be attached via a microscope plugin. As a result of this, the ``MicroscopeViewPlugin`` class has a ``self.microscope`` attribute, allowing direct access to the :py:class:`openflexure_microscope.Microscope` object. This means that web API plugins can simply chain together basic microscope functions and expose new API routes. No additional microscope functionality is required. However, in most cases web API plugins will serve to provide API routes to new microscope functionality defined in a microscope plugin.


Tasks and Locks
---------------
Two principles have been implemented to regulate and synchronise access to the microscope hardware: tasks, and locks.
Especially when writing plugins with API routes, careful use of both tasks and locks should be implemented.

Tasks
+++++
Tasks are introduced to manage long-running functions in a way that does not block HTTP requests. Without
the use of tasks, long-running functions would block an HTTP response until the function returns, often 
resulting in a timeout.

To prevent this, any function can be offloaded to a background task. This is done through the microscope's ``task`` object,
by calling ``<microscope>.task.start(<long_running_function>, *args, **kwargs)``. Internally, the ``task`` object stores a list
of all requested tasks, which themselves contain a ``state`` dictionary. This dictionary stores the status of the task (if it
is idle, running, error, or success), information about the start and end times, a unique task ID, and the return value of 
the long-running function. 

By using tasks, a function can be started in the background, and it's return value fetched at a later time once it has reported
success. If a long-running task is started by some client, it should note the ID returned in the task state JSON, and use this to
periodically check on the status of that particular task. API routes have been created to allow checking the state of all tasks 
(GET `/task`), a particular task by ID (GET `/task/<task_id>`), removing individual tasks (DELETE `/task/<task_id>`), and pruning 
the task list of any no-longer-running tasks (DELETE `/task`).

An example of a long running task may look like:

.. code-block:: python

    from openflexure_microscope.plugins import MicroscopeViewPlugin
    from openflexure_microscope.exceptions import TaskDeniedException

    class MyPlugin(MicroscopeViewPlugin):
        def post(self):
            # Attach the long-running method as a microscope task
            try:
                self.my_task = self.microscope.task.start(self.plugin.long_running_function)
                return jsonify(self.my_task.state), 202

            except TaskDeniedException:
                return abort(409)

After some time, once the task has completed, it could be retreived using:

.. code-block:: python

    ...
    def get_result(self):
        self.my_task.state['status'] == "success":
            return self.my_task.state['return']

Locks
+++++
Locks have been implemented to solve a distinct issue, most obvious when considering long-running tasks. During
a long task such as a tile-scan or autofocus, it is absolutely necesarry to block any completing interaction with
the microscope hardware. For example, even if the stage is not actively moving (for example during a capture phase
within a tile scan), another user should not be able to move the microscope, interrupting the task. Thread locks act
to prevent this.

The camera and stage both contain an instance of :py:class:`openflexure_microscope.lock.StrictLock`, named ``lock``.
Built-in functions such as capture and move will always acquire this lock for the duration of the function. This ensures
that, for example, simultaneous attemps to move do not occur.

More importantly, however, tasks can hold on to these locks for longer periods of time, blocking any other calls to the hardware.

For example, a timelapse plugin may look like:

.. code-block:: python

    from openflexure_microscope.plugins import MicroscopePlugin
    from openflexure_microscope.exceptions import TaskDeniedException
    from openflexure_microscope.api.v1.views import MicroscopeViewPlugin
    from openflexure_microscope.api.utilities import JsonResponse


    ### MICROSCOPE PLUGIN ###

    class MyPluginClass(MicroscopePlugin):

        api_views = {
            '/timelapse': TimelapseAPI,
        }

        def timelapse(self, n_images):
            """
            Demonstrate a long-running method that requires microscope hardware
            """
            print("Starting timelapse...")
            capture_array = []  # Empty list to store captures in

            # Acquire locks. Exception is raised if lock is in use by another thread.
            with self.microscope.camera.lock, self.microscope.stage.lock:
                for _ in range(n_images):

                    # Create a data stream to capture to
                    output = self.microscope.camera.new_image(
                        temporary=False)

                    # Capture a still image from the Pi camera, into the data stream
                    self.microscope.camera.capture(
                        output.file,
                        use_video_port=True)
                    
                    # Append the capture data to our list
                    capture_array.append(output)

                    # Wait for 1 minute
                    time.sleep(60)  

            return capture_array


    ### API ROUTES ###

    class TimelapseAPI(MicroscopeViewPlugin):
        def post(self):

            # Get any JSON data in the body of the POST request
            payload = JsonPayload(request)

            # Extract the "n_images" parameter if it was passed. Otherwise, default to 10.
            n_images = payload.param('n_images', default=10, convert=int)

            # Attach the long-running method as a microscope task
            self.timelapse_task = self.microscope.task.start(self.plugin.timelapse, n_images)

            # Return the state of the task (will show ID, start time, and status before the task has finished)
            return jsonify(self.timelapse_task.state), 202


Notice that even though we never use the stage here, we still acquire the lock. This means that during the timelapse, 
no other user is able to move the stage, or take separate captures. Control of the microscope is handed exclusively 
to the thread that obtains the lock, which in this case is the thread spawned when handling a POST request:
``self.microscope.task.start(self.plugin.timelapse, n_images)``.
