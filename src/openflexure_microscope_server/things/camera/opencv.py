"""OpenFlexure Microscope OpenCV Camera.

This module defines a camera Thing that uses OpenCV's
``VideoCapture``.

See repository root for licensing information.
"""

from __future__ import annotations
import io
import json
import logging
from typing import Literal, Optional
from threading import Thread

import cv2
import piexif

import labthings_fastapi as lt
from labthings_fastapi.types.numpy import NDArray

from . import BaseCamera, JPEGBlob


class OpenCVCamera(BaseCamera):
    """A Thing that provides and interface to an OpenCV Camera."""

    def __init__(self, camera_index: int = 0):
        """Iniatilise the thing storing the index of the camera to use.

        :param camera_index: The index of the camera to use for the microscope.
        """
        self.camera_index = camera_index
        self._capture_thread: Optional[Thread] = None
        self._capture_enabled = False

    def __enter__(self):
        """Start the capture thread when the Thing context manager is opened."""
        self.cap = cv2.VideoCapture(self.camera_index)
        self._capture_enabled = True
        self._capture_thread = Thread(target=self._capture_frames)
        self._capture_thread.start()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        """Release the camera when the Thing context manager is closed.

        Before releasing the camera the capture thread is closed.
        """
        if self.stream_active:
            self._capture_enabled = False
            self._capture_thread.join()
        self.cap.release()

    @lt.thing_property
    def stream_active(self) -> bool:
        """Whether the MJPEG stream is active."""
        if self._capture_enabled and self._capture_thread:
            return self._capture_thread.is_alive()
        return False

    def _capture_frames(self):
        portal = lt.get_blocking_portal(self)
        while self._capture_enabled:
            ret, frame = self.cap.read()
            if not ret:
                logging.error(
                    f"Failed to capture frame from camera {self.camera_index}"
                )
                break
            jpeg = cv2.imencode(".jpg", frame)[1].tobytes()
            self.mjpeg_stream.add_frame(jpeg, portal)
            jpeg_lores = cv2.imencode(".jpg", cv2.resize(frame, (320, 240)))[
                1
            ].tobytes()
            self.lores_mjpeg_stream.add_frame(jpeg_lores, portal)

    @lt.thing_action
    def capture_array(
        self,
        resolution: Literal["main", "full"] = "full",
    ) -> NDArray:
        """Acquire one image from the camera and return as an array.

        This function will produce a nested list containing an uncompressed RGB image.
        It's likely to be highly inefficient - raw and/or uncompressed captures using
        binary image formats will be added in due course.
        """
        logging.warning(f"OpenCV camera doesn't respect {resolution} setting")
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError(
                f"Failed to capture frame from camera {self.camera_index}"
            )
        return frame

    @lt.thing_action
    def capture_jpeg(
        self,
        metadata_getter: lt.deps.GetThingStates,
        resolution: Literal["main", "full"] = "main",
    ) -> JPEGBlob:
        """Acquire one image from the camera and return as a JPEG blob.

        This function will produce a JPEG image.
        """
        logging.warning(f"OpenCV camera doesn't respect {resolution} setting")
        frame = self.capture_array()
        jpeg = cv2.imencode(".jpg", frame)[1].tobytes()
        exif_dict = {
            "Exif": {
                piexif.ExifIFD.UserComment: json.dumps(metadata_getter()).encode(
                    "utf-8"
                )
            },
            "GPS": {},
            "Interop": {},
            "1st": {},
            "thumbnail": None,
        }
        output = io.BytesIO()
        piexif.insert(piexif.dump(exif_dict), jpeg, output)
        return JPEGBlob.from_bytes(output.getvalue())
