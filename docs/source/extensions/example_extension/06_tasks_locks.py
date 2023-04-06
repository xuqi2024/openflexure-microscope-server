import time  # Used in our timelapse function

from labthings import current_action, fields, find_component, update_action_progress
from labthings.extensions import BaseExtension
from labthings.views import ActionView

# Used in our timelapse function
from openflexure_microscope.captures.capture_manager import generate_basename


# Create the extension class
class TimelapseExtension(BaseExtension):
    def __init__(self):
        # Superclass init function
        super().__init__("org.openflexure.timelapse-extension", version="0.0.0")

        # Add our API views
        self.add_view(TimelapseAPIView, "/timelapse")

    def timelapse(self, microscope, n_images, t_between):
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
                # Elegantly handle action cancellation
                if current_action() and current_action().stopped:
                    return
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
                update_action_progress(progress_pct)

                # Wait for the specified time
                time.sleep(t_between)


## Extension views


class TimelapseAPIView(ActionView):
    """
    Take a series of images in a timelapse
    """

    args = {
        "n_images": fields.Integer(
            required=True, metadata={"example": 5, "description": "Number of images"}
        ),
        "t_between": fields.Number(
            load_default=1,
            metadata={"example": 1, "description": "Time (seconds) between images"},
        ),
    }

    def post(self, args):
        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Start "timelapse"
        return self.extension.timelapse(
            microscope, args.get("n_images"), args.get("t_between")
        )


LABTHINGS_EXTENSIONS = (TimelapseExtension,)
