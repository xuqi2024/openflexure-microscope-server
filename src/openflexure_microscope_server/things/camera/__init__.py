"""OpenFlexure Microscope Camera

This module defines the interface for cameras. Any compatible Thing
should enabe the server to work.

See repository root for licensing information.
"""

from __future__ import annotations
import logging
from typing import Literal, Protocol, runtime_checkable, Optional

from pydantic import RootModel

from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.dependencies.blocking_portal import BlockingPortal
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.raw_thing import raw_thing_dependency
from labthings_fastapi.outputs.mjpeg_stream import MJPEGStreamDescriptor
from labthings_fastapi.outputs.blob import Blob
from labthings_fastapi.types.numpy import NDArray


class JPEGBlob(Blob):
    media_type: str = "image/jpeg"

class PNGBlob(Blob):
    media_type: str = "image/png"

class ArrayModel(RootModel):
    """A model for an array"""
    root: NDArray

class BaseCamera(Thing):
    """A stub for a camera, to allow dependencies


    As of LabThings-FastAPI 0.0.7, we can't make a thing client dependency
    based on a protocol, because the protocol is not a Thing, and its
    methods/properties are not decorated as Affordances. This stub class
    is a workaround for that limitation, and should not be used directly.

    This stub class should be used for dependencies on the CameraProtocol.
    """

    mjpeg_stream = MJPEGStreamDescriptor()
    lores_mjpeg_stream = MJPEGStreamDescriptor()

    def __enter__(self) -> None:
        raise NotImplementedError("CameraThings must define their own __enter__ method")

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    @thing_property
    def stream_active(self) -> bool:
        "Whether the MJPEG stream is active"
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    @thing_action
    def capture_array(
        self,
        stream_name: Literal["main", "lores", "raw", "full"] = "main",
        wait: Optional[float] = 5,
    ) -> NDArray:
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    @thing_action
    def capture_jpeg(
        self,
        metadata_getter: GetThingStates,
        resolution: Literal["lores", "main", "full"] = "main",
        wait: Optional[float] = 5,
    ) -> JPEGBlob:
        """Acquire one image from the camera and return as a JPEG blob"""
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    @thing_action
    def start_streaming(self, main_resolution, buffer_count) -> None:
        """Start (or stop and restart) the camera with the given resolution
        for the main stream, and buffer_count number of images in the buffer"""
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    @thing_action
    def capture_image(self, stream_name, wait):
        """Capture a PIL image from stream stream_name with timeout wait"""
        raise NotImplementedError("Cameras must not inherit from CameraStub")


CameraDependency = direct_thing_client_dependency(BaseCamera, "/camera/")
RawCameraDependency = raw_thing_dependency(BaseCamera)
