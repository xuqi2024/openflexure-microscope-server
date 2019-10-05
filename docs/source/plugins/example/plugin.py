from openflexure_microscope.plugins import MicroscopePlugin
from openflexure_microscope.api.v1.views import MicroscopeViewPlugin
from openflexure_microscope.api.utilities import JsonResponse

import os
import time
import json

from flask import request, Response, escape, jsonify

HERE = os.path.dirname(os.path.realpath(__file__))
FORM_PATH = os.path.join(HERE, "forms.json")

### MICROSCOPE PLUGIN ###


class MyPluginClass(MicroscopePlugin):
    """
    A set of default plugins
    """

    global FORM_PATH

    with open(FORM_PATH, "r") as sc:
        api_form = json.load(sc)

    api_views = {
        "/identify": IdentifyAPI,
        "/hello": HelloWorldAPI,
        "/timelapse": TimelapseAPI,
    }

    def identify(self):
        """
        Demonstrate access to Microscope.camera, and Microscope.stage
        """

        response = "My parent camera is {}, and my parent stage is {}.".format(
            self.microscope.camera, self.microscope.stage
        )
        return response

    def hello_world(self):
        """
        Demonstrate passive method
        """

        return "Hello world!"

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
                    temporary=False
                )

                # Capture a still image from the Pi camera, into the data stream
                self.microscope.camera.capture(output.file, use_video_port=True)

                # Append the capture data to our list
                capture_array.append(output)

                # Wait for 1 minute
                time.sleep(60)


### API VIEWS ###


class IdentifyAPI(MicroscopeViewPlugin):
    """
    A simple example API plugin, attached through the main microscope plugin.
    """

    def get(self):
        """
        Method to call when an HTTP GET request is made.
        """
        # Call a method from our plugin, using the MicroscopeViewPlugin.plugin shortcut
        data = self.plugin.identify()
        return Response(escape(data))


class HelloWorldAPI(MicroscopeViewPlugin):
    """
    A method to create, set, and return a new microscope parameter.
    """

    def get(self):
        """
        Method to call when an HTTP GET request is made.
        """

        # If the microscope does not already contain our plugin_string attribute
        if not hasattr(self.microscope, "plugin_string"):
            # Make a string, using the MicroscopeViewPlugin.plugin shortcut
            self.microscope.plugin_string = self.plugin.hello_world()

        json_response = jsonify({"plugin_string": self.microscope.plugin_string})

        return Response(json_response)

    def post(self):
        """
        Method to call when an HTTP POST request is made. 
        Assumes request will include a JSON payload.
        """
        # Get payload JSON
        payload = JsonResponse(request)

        # Extract a value from the JSON key 'plugin_string', and convert to a string. If no value is given, default to empty.
        new_plugin_string = payload.param("plugin_string", default="", convert=str)

        if new_plugin_string:  # If not None or empty
            # Set microscope attribute to the specified string
            self.microscope.plugin_string = new_plugin_string

        json_response = jsonify({"plugin_string": self.microscope.plugin_string})

        return Response(json_response)


class TimelapseAPI(MicroscopeViewPlugin):
    def post(self):

        # Get any JSON data in the body of the POST request
        payload = JsonResponse(request)

        # Extract the "n_images" parameter if it was passed. Otherwise, default to 10.
        n_images = payload.param("n_images", default=10, convert=int)

        # Attach the long-running method as a microscope task
        self.timelapse_task = self.microscope.task.start(
            self.plugin.timelapse, n_images
        )

        # Return the state of the task (will show ID, start time, and status before the task has finished)
        return jsonify(self.timelapse_task.state), 202
