# -*- coding: utf-8 -*-

from __future__ import division

import logging
import threading
import time
from datetime import datetime
from io import BytesIO

# Type hinting
from typing import BinaryIO, Optional, Tuple, Union

from PIL import Image, ImageDraw

from openflexure_microscope.camera.base import BaseCamera

# PIL spams the logger with debug-level information. This is a pain when debugging api.app.
# We override the logging settings in api.app by setting a level for PIL here.

pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.INFO)


# MAIN CLASS
class MissingCamera(BaseCamera):
    def __init__(self):
        # Run BaseCamera init
        BaseCamera.__init__(self)

        # Update config properties
        self.image_resolution: Tuple[int, int] = (1312, 976)
        self.stream_resolution: Tuple[int, int] = (640, 480)
        self.numpy_resolution: Tuple[int, int] = (1312, 976)
        self.jpeg_quality: int = 75
        self.framerate: int = 10

        self.badframe = False

        # Generate an initial dummy image
        self.generate_new_dummy_image()

        # Start streaming
        self.stop: bool = False  # Used to indicate that the stream loop should break
        self.start_worker()
        # Wait until frames are available
        logging.info("Waiting for frames")
        self.stream.new_frame.wait()

    def generate_new_dummy_image(self, truncate: bool = False):
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

        output = BytesIO()
        image.save(output, format="JPEG")
        data = output.getvalue()
        if truncate:
            print("Truncating frame data")
            data = data[:-4]
        self.stream.write(data)

    def start_worker(self, **_) -> bool:
        """Start the background camera thread if it isn't running yet."""
        self.stop = False

        if not self.stream_active:
            # Start background frame thread
            self.thread = threading.Thread(target=self._thread)
            self.thread.daemon = True
            self.thread.start()
        return True

    def stop_worker(self, timeout: int = 5) -> bool:
        """Flag worker thread for stop. Waits for thread close or timeout."""
        logging.debug("Stopping worker thread")
        timeout_time = time.time() + timeout

        if self.stream_active:
            self.stop = True
            self.thread.join()  # Wait for stream thread to exit
            logging.debug("Waiting for stream thread to exit.")

        while self.stream_active:
            if time.time() > timeout_time:
                logging.debug("Timeout waiting for worker thread close.")
                raise TimeoutError("Timeout waiting for worker thread close.")
            else:
                time.sleep(0.1)
        return True

    def _thread(self):
        """Camera background thread."""
        # Set the camera object's frame iterator
        logging.debug("Entering worker thread.")

        self.stream_active = True

        i = 0

        while True:
            # Only serve frames at 1fps
            time.sleep(1)
            i += 1
            # Toggle between good and bad frames
            if i >= 5:
                i = 0
                self.badframe = not self.badframe
            # Generate new dummy image
            self.generate_new_dummy_image(truncate=self.badframe)

            try:
                if self.stop is True:
                    logging.debug("Worker thread flagged for stop.")
                    break

            except AttributeError:
                pass

        logging.debug("BaseCamera worker thread exiting...")
        # Set stream_activate state
        self.stream_active = False

    @property
    def configuration(self):
        """The current camera configuration."""
        return {}

    @property
    def state(self):
        """The current read-only camera state."""
        return {}

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
        conf_dict = {
            "stream_resolution": self.stream_resolution,
            "image_resolution": self.image_resolution,
            "numpy_resolution": self.numpy_resolution,
            "jpeg_quality": self.jpeg_quality,
        }

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

    def set_zoom(self, *_, **__) -> None:
        """
        Change the camera zoom, handling re-centering and scaling.
        """
        logging.info("Zoom not implemented in mock camera")

    def start_stream(self):
        pass

    def stop_stream(self):
        pass

    def start_preview(self, *_, **__):
        """Start the on board GPU camera preview."""
        logging.info("GPU preview not implemented in mock camera")

    def stop_preview(self):
        """Stop the on board GPU camera preview."""
        logging.info("GPU preview not implemented in mock camera")

    def start_recording(self, *_, **__):
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
        output: Union[str, BinaryIO],
        fmt: str = "jpeg",
        use_video_port: bool = False,
        resize: Optional[Tuple[int, int]] = None,
        bayer: bool = True,
        thumbnail: Optional[Tuple[int, int, int]] = None,
    ):
        """
        Capture a still image to a StreamObject.

        Defaults to JPEG format.
        Target object can be overridden for development purposes.

        Args:
            output: String or file-like object to write capture data to
        """

        with self.lock:
            if isinstance(output, str):
                output = open(output, "wb")

            output.write(self.stream.getvalue())

            if isinstance(output, str):
                output.close()
            else:
                output.flush()
