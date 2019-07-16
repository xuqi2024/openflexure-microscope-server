# -*- coding: utf-8 -*-

"""
"""

from __future__ import division

import io
import time
import numpy as np
from PIL import Image

import logging

# Type hinting
from typing import Tuple

from .base import BaseCamera, CaptureObject


# MAIN CLASS
class MockStreamer(BaseCamera):

    def __init__(self):
        # Run BaseCamera init
        BaseCamera.__init__(self)

        # Store state of PiCameraStreamer
        self.state.update({
            'stream_active': False,
            'record_active': False
        })

        # Update config properties
        self.image_resolution = (1312, 976)
        self.stream_resolution = (640, 480)
        self.numpy_resolution = (1312, 976)
        self.jpeg_quality = 75
        self.framerate = 10

        # Create an empty stream
        self.stream = io.BytesIO()

        # Start streaming
        self.start_worker()

    def initialisation(self):
        """Run any initialisation code when the frame iterator starts."""
        pass

    def close(self):
        """Close the Raspberry Pi PiCameraStreamer."""
        # Run BaseCamera close method
        BaseCamera.close(self)

    # HANDLE SETTINGS
    def read_config(self) -> dict:
        """
        Return config dictionary of the PiCameraStreamer.
        """

        conf_dict = {
            'stream_resolution': self.stream_resolution,
            'image_resolution': self.image_resolution,
            'numpy_resolution': self.numpy_resolution,
            'jpeg_quality': self.jpeg_quality
        }

        return conf_dict

    def apply_config(self, config: dict):
        """
        Write a config dictionary to the PiCameraStreamer config.

        The passed dictionary may contain other parameters not relevant to
        camera config. Eg. Passing a general config file will work fine.

        Args:
            config (dict): Dictionary of config parameters.
        """
        # TODO: Include timing and batching logic when applying PiCamera settings

        paused_stream = False
        logging.debug("PiCameraStreamer: Applying config:")
        logging.debug(config)

        with self.lock:

            # Apply valid config params to Picamera object
            if not self.state['record_active']:  # If not recording a video

                # PiCameraStreamer parameters
                for key, value in config.items():  # For each provided setting
                    if hasattr(self, key):
                        setattr(self, key, value)

                # If stream was paused to update config, unpause
                if paused_stream:
                    logging.info("Resuming stream.")
                    self.start_stream_recording()

            else:
                raise Exception(
                    "Cannot update camera config while recording is active.")

    def set_zoom(self, zoom_value: float = 1.) -> None:
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


    def start_recording(
            self,
            output,
            fmt: str = 'h264',
            quality: int = 15):
        """Start recording.

        Start a new video recording, writing to a output object.

        Args:
            output (CaptureObject/str): Output object to write data bytes to.
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
            fmt: str = 'jpeg',
            use_video_port: bool = False,
            resize: Tuple[int, int] = None,
            bayer: bool = True):
        """
        Capture a still image to a StreamObject.

        Defaults to JPEG format.
        Target object can be overridden for development purposes.

        Args:
            output (CaptureObject/str): Output object to write data bytes to.
            use_video_port (bool): Capture from the video port used for streaming. Lower resolution, faster.
            fmt (str): Format of the capture.
            resize ((int, int)): Resize the captured image.
            bayer (bool): Store raw bayer data in capture
        """

        with self.lock:
            logging.warning("Capture not implemented in mock camera")


    def gen_img(self):
        imarray = np.random.rand(self.stream_resolution[1], self.stream_resolution[0], 3) * 255
        im = Image.fromarray(imarray.astype('uint8')).convert('L')
        im.save(self.stream, format="JPEG")

    # HANDLE STREAM FRAMES

    def frames(self):
        """
        Create generator that returns frames from the camera.

        Records video from port 1 to a byte stream,
        and iterates sequential frames.
        """
        # Run this initialisation method
        self.initialisation()

        # Update state
        logging.debug("STREAM ACTIVE")

        # While the iterator is not closed
        try:
            while True:
                # reset stream for next frame
                self.stream.seek(0)
                self.stream.truncate()
                # to stream, read the new frame
                time.sleep(1 / self.framerate * 0.1)

                # yield the result to be read
                self.gen_img()
                frame = self.stream.getvalue()

                # ensure the size of package is right
                if len(frame) == 0:
                    pass
                else:
                    yield frame

        # When GeneratorExit or StopIteration raised, run cleanup code
        finally:
            logging.debug("FRAME ITERATOR END")
