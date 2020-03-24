# -*- coding: utf-8 -*-

"""
"""

from __future__ import division

import io
import time
import numpy as np
from PIL import Image, ImageFont, ImageDraw
from datetime import datetime

import logging

# Type hinting
from typing import Tuple

from openflexure_microscope.camera.base import BaseCamera, CaptureObject


"""
PIL spams the logger with debug-level information. This is a pain when debugging api.app.
We override the logging settings in api.app by setting a level for PIL here.
"""
pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)


# MAIN CLASS
class MissingCamera(BaseCamera):
    def __init__(self):
        # Run BaseCamera init
        BaseCamera.__init__(self)

        # Update config properties
        self.image_resolution = (1312, 976)
        self.stream_resolution = (640, 480)
        self.numpy_resolution = (1312, 976)
        self.jpeg_quality = 75
        self.framerate = 10

        # Create an empty stream
        self.stream = io.BytesIO()

        # Generate an initial dummy image
        self.generate_new_dummy_image()

        # Start streaming
        self.start_worker()

    def generate_new_dummy_image(self):
        # Create a dummy image to serve in the stream
        image = Image.new(
            "RGB",
            (self.stream_resolution[0], self.stream_resolution[1]),
            color=(0, 0, 0),
        )

        draw = ImageDraw.Draw(image)
        draw.text(
            (20, 70),
            "Camera disconnected: {}".format(
                datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
            ),
        )

        image.save(self.stream, format="JPEG")

    @property
    def configuration(self):
        """The current camera configuration."""
        return {}

    @property
    def state(self):
        """The current read-only camera state."""
        return {}

    def initialisation(self):
        """Run any initialisation code when the frame iterator starts."""
        pass

    def close(self):
        """Close the Raspberry Pi PiCameraStreamer."""
        # Run BaseCamera close method
        BaseCamera.close(self)

    # HANDLE SETTINGS
    def read_settings(self) -> dict:
        """
        Return config dictionary of the PiCameraStreamer.
        """

        # Get config items from the base class
        conf_dict = BaseCamera.read_settings(self)

        # Include device-specific config items
        conf_dict.update(
            {
                "stream_resolution": self.stream_resolution,
                "image_resolution": self.image_resolution,
                "numpy_resolution": self.numpy_resolution,
                "jpeg_quality": self.jpeg_quality,
            }
        )

        return conf_dict

    def update_settings(self, config: dict):
        """
        Write a config dictionary to the PiCameraStreamer config.

        The passed dictionary may contain other parameters not relevant to
        camera config. Eg. Passing a general config file will work fine.

        Args:
            config (dict): Dictionary of config parameters.
        """
        logging.debug("MockStreamer: Applying config:")
        logging.debug(config)

        with self.lock:

            # Apply valid config params to camera object
            if not self.record_active:  # If not recording a video

                for key, value in config.items():  # For each provided setting
                    if hasattr(self, key):
                        setattr(self, key, value)

            else:
                raise Exception(
                    "Cannot update camera config while recording is active."
                )

    def set_zoom(self, zoom_value: float = 1.0) -> None:
        """
        Change the camera zoom, handling re-centering and scaling.
        """
        logging.warning("Zoom not implemented in mock camera")

    # LAUNCH ACTIONS

    def start_preview(self, fullscreen=True, window=None):
        """Start the on board GPU camera preview."""
        logging.warning("GPU preview not implemented in mock camera")

    def stop_preview(self):
        """Stop the on board GPU camera preview."""
        logging.warning("GPU preview not implemented in mock camera")

    def start_recording(self, output, fmt: str = "h264", quality: int = 15):
        """Start recording.

        Start a new video recording, writing to a output object.

        Args:
            output: String or file-like object to write capture data to
            fmt (str): Format of the capture.
            quality (int): Video recording quality.

        Returns:
            output_object (str/BytesIO): Target object.

        """
        with self.lock:
            # Start recording method only if a current recording is not running
            logging.warning("Recording not implemented in mock camera")

    def stop_recording(self):
        """Stop the last started video recording on splitter port 2."""
        with self.lock:
            logging.warning("Recording not implemented in mock camera")

    def capture(
        self,
        output,
        fmt: str = "jpeg",
        use_video_port: bool = False,
        resize: Tuple[int, int] = None,
        bayer: bool = True,
    ):
        """
        Capture a still image to a StreamObject.

        Defaults to JPEG format.
        Target object can be overridden for development purposes.

        Args:
            output: String or file-like object to write capture data to
            use_video_port (bool): Capture from the video port used for streaming. Lower resolution, faster.
            fmt (str): Format of the capture.
            resize ((int, int)): Resize the captured image.
            bayer (bool): Store raw bayer data in capture
        """

        if isinstance(output, CaptureObject):
            target = output.file
        else:
            target = output

        with self.lock:
            if isinstance(target, str):
                target = open(target, "wb")

            target.write(self.stream.getvalue())

            if isinstance(target, str):
                target.close()

    # HANDLE STREAM FRAMES

    def frames(self):
        """
        Create generator that returns frames from the camera.
        """
        # Run this initialisation method
        self.initialisation()

        # Update state
        logging.debug("STREAM ACTIVE")

        # While the iterator is not closed
        try:
            while True:
                time.sleep(1)  # Only serve frames at 1fps
                # Reset stream
                self.stream.seek(0)
                self.stream.truncate()

                # Generate new dumm image
                self.generate_new_dummy_image()
                # Get frame data
                frame = self.stream.getvalue()

                # ensure the size of package is right
                if len(frame) == 0:
                    pass
                else:
                    yield frame

        # When GeneratorExit or StopIteration raised, run cleanup code
        finally:
            logging.debug("FRAME ITERATOR END")
