"""Thread module that propagates exceptions and return values.

This module provides a Thread subclass that captures exceptions and return values
from the target function, allowing them to be retrieved in the parent thread.
"""

from threading import Thread

class PropagatingThread(Thread):
    """A Thread subclass that propagates exceptions and captures return values.

    This class extends threading.Thread to capture any exceptions raised in the
    thread and the return value of the target function, making them accessible
    from the parent thread.
    """
    def __init__(self, *args, **kwargs):
        """Initialize the PropagatingThread.

        Args:
            *args: Variable length argument list passed to Thread.__init__.
            **kwargs: Arbitrary keyword arguments passed to Thread.__init__.
        """
        super(PropagatingThread, self).__init__(*args, **kwargs)
        self.exc = None
        self.ret = None
        self._finished = False

    def run(self):
        """Execute the thread's target function and capture exceptions and return value.

        This method overrides Thread.run() to capture any exceptions raised during
        execution and the return value of the target function.
        """
        try:
            if hasattr(self, '_Thread__target'):
                self.ret = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
            else:
                self.ret = self._target(*self._args, **self._kwargs)
        except BaseException as e:
            self.exc = e
        finally:
            self._finished = True

    def is_finished(self):
        """Check if the thread has finished execution.

        Returns:
            bool: True if the thread has finished, False otherwise.
        """
        return self._finished

    def check_exception(self):
        """Check and raise any exception that occurred in the thread.

        Raises:
            BaseException: The exception that was raised in the thread, if any.
        """
        if self.exc:
            raise self.exc

    def result(self):
        """Get the return value of the thread's target function.

        Returns:
            Any: The return value of the target function.

        Raises:
            BaseException: If an exception occurred in the thread.
        """
        self.check_exception()
        return self.ret
