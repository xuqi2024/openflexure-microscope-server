from threading import Thread
import datetime
import logging
import traceback
import uuid

from openflexure_microscope.exceptions import TaskDeniedException
from openflexure_microscope.utilities import entry_by_id


class TaskOrchestrator:
    """
    Class responsible for spawning threaded tasks, and storing their returns.
    A microscope should contain exactly one instance of `TaskOrchestrator`.

    Attributes:
        tasks (list): List of `Task` objects

    """
    def __init__(self):
        self.tasks = []

    @property
    def state(self):
        """
        Returns a list of dictionary representations of all tasks in the session.
        """
        state = {}

        for task in self.tasks:
            state[task.id] = task.state

        return state

    def task_from_id(self, task_id: str):
        """
        Returns a particular task object with the specified `task_id`.
        """
        return entry_by_id(task_id, self.tasks)

    def start(self, function, *args, **kwargs):
        """
        Attach and start a new long-running task, if allowed by `start_condition()`.
        Returns an instance of :py:class:`openflexure_microscope.task.Task`, which can be used to check the state
        or eventual return of the task.

        Args:
            function (function): The target function to run in the background
            args, kwargs: Arguments that will be passed to `function` at runtime.
        """
        # Create a task object
        task = Task(function, *args, **kwargs)

        # If the task isn't allowed to run
        if not self.start_condition(task):
            raise TaskDeniedException("Unable to start this task. Aborting.")
        else:
            self.tasks.append(task)
            task.start()
            return task

    def clean(self):
        """
        Remove all inactive tasks from the task array.
        This will remove tasks that either finished or never started.
        """
        self.tasks = [task for task in self.tasks if task._running]

    def delete(self, task_id):
        """
        Delete a given task by ID, only if task is not currently running.
        """
        success = False

        for task in self.tasks:
            if task.id == task_id and not task._running:
                self.tasks.remove(task)
                success = True

        return success

    def start_condition(self, task_obj):
        """
        Method returning bool describing if a particular task is allowed to run.
        Currently always allows tasks to start, as locks determine access to hardware.
        """
        # return not any([task._running for task in self.tasks])
        return True


class Task:
    """
    Class responsible for running a task function in a thread, and handling return or errors.
    Tasks should be created by an instance of :py:class:`openflexure_microscope.task.TaskOrchestrator`.

    Args:
        function (function): Function to be called in the task thread.

    Attributes:
        task (function): Function to be called in the task thread.
        args: Positional arguments to be passed to the task function
        kwargs: Keyword arguments to be passed to the task function.
        _running (bool): If task is currently running
        id (str): Unique ID for the task
        state (dict): Dictionary describing the full state of the task.
            `status` will be one of 'idle'', 'running', 'error', or 'success'.
            `return` eventually holds the return value of the task function.
    """
    def __init__(self, function, *args, **kwargs):
        # The task long-running method
        self.task = function
        self.args = args
        self.kwargs = kwargs

        self._running = False

        self.id = uuid.uuid4().hex

        self.state = {
            'id': self.id,
            'status': 'idle',
            'return': None,
            'start_time': None,
            'end_time': None,
        }

    def process(self, f):
        """
        Wraps the target function to handle recording `status` and `return` to `state`.
        """
        def wrapped(*args, **kwargs):
            self.state['status'] = 'running'
            try:
                r = f(*args, **kwargs)
                s = 'success'
            except Exception as e:
                logging.error(e)
                logging.error(traceback.format_exc())
                r = str(e)
                s = 'error'
            self.state['return'] = r
            self.state['status'] = s
        return wrapped

    def run(self):
        """
        Records the task start and end times to `state`, and runs the task wrapped in `process`.
        """
        self.state['start_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        self.process(self.task)(*self.args, **self.kwargs)
        self._running = False
        self.state['end_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")

    def start(self):  # Start and draw
        """
        Spawns a thread, and starts `run()` in that thread.
        """
        # If not already running
        if not self._running:
            self._running = True  # Set start command
            thread = Thread(target=self.run)  # Define thread
            thread.daemon = True  # Stop this thread when main thread closes
            thread.start()  # Start thread
