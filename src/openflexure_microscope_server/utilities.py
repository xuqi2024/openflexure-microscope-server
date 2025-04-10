"""
This module contains some utility functions and classes
"""

from threading import Thread


class ErrorCapturingThread(Thread):
    """
    This is a a subclass or Thread. It wraps the target function in a
    try-except block.

    Execution will stop with an unhandled exception, but the exception will not be raised
    until the join method is called. When the join method is called, the exception is
    called in the calling thread.

    This allows for error handling to be performed by the calling thread at the time that
    join is run.
    """

    def __init__(self, group=None, target=None, args=None, kwargs=None, daemon=None):
        """
        Initialise with the same arguments as Thread
        """
        # As all inputs are keywords we need to set the default values for args and kwargs:
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}

        # Make an empty list for any error.
        # We are only ever going to have one or zero errors, this is an empty
        # list as we need to pass the reference not the value to collect the
        # error. If we could simply make a pointer we would have done that.
        self._error_buffer = []

        # Add the target function end error buffer to the thread to the start of
        # the argument list so they are passed to _wrap_and_catch_errors()
        args = (target, self._error_buffer, *args)
        # Start the thread with _wrap_and_catch_errors() as the target
        super().__init__(
            group=group,
            target=_wrap_and_catch_errors,
            args=args,
            kwargs=kwargs,
            daemon=daemon,
        )

    def join(self, timeout=None):
        """
        Join when the thread is complete. If the thread ended due to an unhandled exception,
        the exception will be raised when this method is called.
        """
        super().join(timeout)
        # If there is an error in the error buffer clear the buffer and raise it
        if self._error_buffer:
            err = self._error_buffer[0]
            self._error_buffer = []
            raise err


def _wrap_and_catch_errors(target, error_buffer, *args, **kwargs):
    """
    This function is designed only to be used by
    ErrorCapturingThread

    It will run a target function in a try-except block
    any errors caught are added to an empty list that
    should be supplied as a keyword argument

    Arguments:
      * target - The target function to call
      * error_buffer - An empty list that is used for returning
          the exception from the thread
      *args: The arguments for the target function
      **kwargs: The Keyword arguments for the target function
    """
    try:
        target(*args, **kwargs)
    except BaseException as e:
        error_buffer.append(e)
