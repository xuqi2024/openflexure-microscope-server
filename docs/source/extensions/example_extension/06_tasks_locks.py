from labthings.server.extensions import BaseExtension
from labthings.server.find import find_component
from labthings.server.view import View

from labthings.server.decorators import (
    use_args,
    marshal_with,
    ThingProperty,
    PropertySchema,
    ThingAction,
    doc_response,
    marshal_task,
)
from labthings.server.schema import Schema
from labthings.server import fields

from flask import send_file  # Used to send images from our server
import io  # Used in our capture action
import time  # Used in our timelapse function

# Used in our timelapse function
from openflexure_microscope.camera.base import generate_basename

# Used to run our timelapse in a background thread
from labthings.core.tasks import taskify, update_task_progress


## Extension methods


def timelapse(microscope, n_images, t_between):
    """
    Save a set of images in a timelapse

    Args:
        microscope: Microscope object
        n_images (int): Number of images to take
        t_between (int/float): Time, in seconds, between sequential captures
    """
    base_file_name = generate_basename()
    folder = "TIMELAPSE_{}".format(base_file_name)

    # Take exclusive control over both the camera and stage
    with microscope.camera.lock, microscope.stage.lock:
        for n in range(n_images):
            # Generate a filename
            filename = f"{base_file_name}_image{n}"
            # Create a file to save the image to
            output = microscope.camera.new_image(
                filename=filename, folder=folder, temporary=False
            )

            # Capture
            microscope.camera.capture(output)

            # Add system metadata
            output.put_metadata(microscope.metadata, system=True)

            # Update task progress (only does anyting if the function is running in a LabThings task)
            progress_pct = ((n + 1) / n_images) * 100  # Progress, in percent
            update_task_progress(progress_pct)

            # Wait for the specified time
            time.sleep(t_between)


## Extension views


@ThingAction
class TimelapseAPI(View):
    """
    Take a series of images in a timelapse, running as a background task
    """

    @marshal_task  # Shorthand for marshaling with a pre-made Task object schema
    @use_args(
        {
            "n_images": fields.Integer(
                required=True, example=5, description="Number of images"
            ),
            "t_between": fields.Number(
                missing=1, example=1, description="Time (seconds) between images"
            ),
        }
    )
    def post(self, args):
        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Create and start "timelapse", running in a background task
        task = taskify(timelapse)(
            microscope, args.get("n_images"), args.get("t_between")
        )

        return task


## Create extension

# Create your extension object
my_extension = BaseExtension("com.myname.timelapse-extension", version="0.0.0")

# Add methods to your extension
my_extension.add_method(timelapse, "timelapse")

# Add API views to your extension
my_extension.add_view(TimelapseAPI, "/timelapse")
