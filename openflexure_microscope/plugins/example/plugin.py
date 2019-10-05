import random
import time
from openflexure_microscope.plugins import MicroscopePlugin

from .api import IdentifyAPI, HelloWorldAPI, LongRunningAPI, SomeExceptionAPI


class Plugin(MicroscopePlugin):
    """
    A set of default plugins
    """

    api_views = {
        "/identify": IdentifyAPI,
        "/hello": HelloWorldAPI,
        "/long_running": LongRunningAPI,
        "/some_exception": SomeExceptionAPI,
    }

    def identify(self):
        """
        Demonstrate access to Microscope.camera, and Microscope.stage
        """

        response = "My parent camera is {}, and my parent stage is {}.".format(
            self.microscope.camera, self.microscope.stage
        )
        print(response)
        return response

    def hello_world(self):
        """
        Demonstrate passive method
        """

        return "Hello world!"

    def some_exception(self):
        """
        Demonstrate some broken plugin method that would be long running
        """
        with self.microscope.lock:
            time.sleep(3)
            result = 15.0 / 0

        return result

    def long_running(self, t_run):
        """
        Demonstrate a long-running method that requires microscope hardware
        """
        print("Starting a long-running task...")
        n_array = []

        print("Acquiring composite microscope lock...")
        with self.microscope.camera.lock, self.microscope.stage.lock:
            for _ in range(t_run):
                n_array.append(random.random())
                time.sleep(1)

            print("Long-running task finished! Releasing locks.")

        return n_array
