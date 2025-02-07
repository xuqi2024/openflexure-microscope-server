"""OpenFlexure Microscope OpenCV Camera

This module defines a Thing that is responsible for using the stage and
camera together to perform an autofocus routine.

See repository root for licensing information.
"""

from __future__ import annotations
import io
import json
import logging
from typing import Literal, Optional
from threading import Thread
import time

import cv2
import numpy as np
import piexif

from labthings_fastapi.utilities import get_blocking_portal
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.outputs.mjpeg_stream import MJPEGStreamDescriptor
from labthings_fastapi.types.numpy import NDArray
from labthings_fastapi.server import ThingServer
from pydantic import RootModel

from . import BaseCamera, JPEGBlob, RawIsArrayCamera
from ..stage import StageProtocol as Stage


class ArrayModel(RootModel):
    """A model for an array"""

    root: NDArray


class SimulatedCamera(BaseCamera, RawIsArrayCamera):
    """A Thing representing an OpenCV camera"""

    _stage: Optional[Stage] = None
    _server: Optional[ThingServer] = None

    def __init__(
        self,
        shape: tuple[int, int, int] = (600, 800, 3),
        glyph_shape: tuple[int, int, int] = (51, 51, 3),
        canvas_shape: tuple[int, int, int] = (3000, 4000, 3),
        frame_interval: float = 0.1,
    ):
        self.shape = shape
        self.glyph_shape = glyph_shape
        self.canvas_shape = canvas_shape
        self.frame_interval = frame_interval
        self._capture_thread: Optional[Thread] = None
        self._capture_enabled = False
        self.generate_sprites()
        self.generate_blobs()
        self.generate_canvas()

    def generate_sprites(self):
        """Generate sprites to populate the image"""
        self.sprites = []
        black = np.zeros(self.glyph_shape, dtype=np.uint8)
        x = np.arange(black.shape[0])
        y = np.arange(black.shape[1])
        rr = np.sqrt((x[:, None] - np.mean(x)) ** 2 + (y[None, :] - np.mean(y)) ** 2)
        for i in [5, 7, 9, 11, 13, 15]:
            sprite = black.copy()
            sprite[rr < i] = 255
            self.sprites.append(sprite)

    def generate_blobs(self, N: int = 1000):
        """Generate coordinates of blobs

        Blobs are characterised by X, Y, sprite
        We also generate a KD tree to rapidly find blobs in an image
        """
        self.blobs = np.zeros((N, 3))
        rng = np.random.default_rng()
        w = np.max(self.glyph_shape)
        self.blobs[:, 0] = rng.uniform(w / 2, self.canvas_shape[0] - w / 2, N)
        self.blobs[:, 1] = rng.uniform(w / 2, self.canvas_shape[1] - w / 2, N)
        self.blobs[:, 2] = rng.choice(len(self.sprites), N)

    def generate_canvas(self):
        """Generate a blank canvas"""
        self.canvas = np.zeros(self.canvas_shape, dtype=np.uint8)
        self.canvas[...] = 255
        w, h, _ = self.glyph_shape
        for x, y, sprite in self.blobs:
            self.canvas[
                int(x) - w // 2 : int(x) - w // 2 + w,
                int(y) - h // 2 : int(y) - h // 2 + h,
            ] -= self.sprites[int(sprite)]

    def generate_image(self, pos: tuple[int, int]):
        """Generate an image with blobs based on supplied coordinates"""
        cw, ch, _ = self.canvas_shape
        w, h, _ = self.shape
        tl = (int(pos[0]) - w // 2 - cw // 2, int(pos[1]) - h // 2 - ch // 2)
        image = self.canvas[
            tuple(slice(tl[i], tl[i] + self.shape[i]) for i in range(2))
            + (slice(None),)
        ]
        if image.shape != self.shape:
            raise ValueError(
                f"Image shape {image.shape} does not match intended shape {self.shape}"
            )
        return image

    def attach_to_server(self, server: ThingServer, path: str):
        self._server = server
        return super().attach_to_server(server, path)

    def get_stage_position(self):
        if not self._stage and self._server:
            self._stage = self._server.things["/stage/"]
        return self._stage.instantaneous_position

    def generate_frame(self):
        """Generate a frame with blobs based on the stage coordinates"""
        try:
            pos = self.get_stage_position()
        except Exception as e:
            print(f"Failed to get stage position: {e}")
            pos = {"x": 0, "y": 0}
        return self.generate_image((pos["x"] / 10, pos["y"] / 10))

    def __enter__(self):
        self._capture_enabled = True
        self._capture_thread = Thread(target=self._capture_frames)
        self._capture_thread.start()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        if self.stream_active:
            self._capture_enabled = False
            self._capture_thread.join()

    @thing_property
    def stream_active(self) -> bool:
        "Whether the MJPEG stream is active"
        if self._capture_enabled and self._capture_thread:
            return self._capture_thread.is_alive()
        return False

    mjpeg_stream = MJPEGStreamDescriptor()
    lores_mjpeg_stream = MJPEGStreamDescriptor()

    def _capture_frames(self):
        portal = get_blocking_portal(self)
        while self._capture_enabled:
            time.sleep(self.frame_interval)
            try:
                frame = self.generate_frame()
                jpeg = cv2.imencode(".jpg", frame)[1].tobytes()
                self.mjpeg_stream.add_frame(jpeg, portal)
                jpeg_lores = cv2.imencode(".jpg", cv2.resize(frame, (320, 240)))[
                    1
                ].tobytes()
                self.lores_mjpeg_stream.add_frame(jpeg_lores, portal)
            except Exception as e:
                logging.error(f"Failed to capture frame: {e}, retrying...")

    @thing_action
    def capture_array(
        self,
        resolution: Literal["main", "full"] = "full",
    ) -> ArrayModel:
        """Acquire one image from the camera and return as an array

        This function will produce a nested list containing an uncompressed RGB image.
        It's likely to be highly inefficient - raw and/or uncompressed captures using
        binary image formats will be added in due course.
        """
        return self.generate_frame()

    @thing_action
    def capture_jpeg(
        self,
        metadata_getter: GetThingStates,
        resolution: Literal["main", "full"] = "main",
    ) -> JPEGBlob:
        """Acquire one image from the camera and return as a JPEG blob

        This function will produce a JPEG image.
        """
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
