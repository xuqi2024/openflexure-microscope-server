"""OpenFlexure Microscope Camera

This module defines the interface for cameras. Any compatible Thing
should enabe the server to work.

See repository root for licensing information.
"""

from __future__ import annotations
import logging
from typing import Literal, Protocol, runtime_checkable, Optional

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


@runtime_checkable
class CameraProtocol(Protocol):
    """A Thing representing a camera"""

    def __enter__(self) -> None: ...

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None: ...

    @property
    def stream_active(self) -> bool:
        "Whether the MJPEG stream is active"
        ...

    def snap_image(self) -> NDArray:
        """Acquire one image from the camera."""
        ...

    def capture_array(
        self,
        stream_name: Literal["main", "lores", "raw", "full"] = "main",
        wait: Optional[float] = 5,
    ) -> NDArray: ...

    def capture_jpeg(
        self,
        metadata_getter: GetThingStates,
        resolution: Literal["lores", "main", "full"] = "main",
        wait: Optional[float] = 5,
    ) -> JPEGBlob:
        """Acquire one image from the camera and return as a JPEG blob"""
        ...

    def grab_jpeg(
        self,
        portal: BlockingPortal,
        stream_name: Literal["main", "lores"] = "main",
    ) -> JPEGBlob:
        """Acquire one image from the preview stream and return as an array

        This differs from `capture_jpeg` in that it does not pause the MJPEG
        preview stream. Instead, we simply return the next frame from that
        stream (either "main" for the preview stream, or "lores" for the low
        resolution preview). No metadata is returned.
        """
        ...

    def grab_jpeg_size(
        self,
        portal: BlockingPortal,
        stream_name: Literal["main", "lores"] = "main",
    ) -> int:
        """Acquire one image from the preview stream and return its size"""
        ...

    
    def start_streaming(self, main_resolution) -> None:
        """Start (or stop and restart) the camera with the given resolution
        for the main stream"""
        ...

class BaseCamera(Thing):
    """A Thing representing a camera

    This is a concrete base class for `Thing`s implementing the `CameraProtocol`.
    It provides the stream descriptors and actions to grab from the stream.
    """

    mjpeg_stream = MJPEGStreamDescriptor()
    lores_mjpeg_stream = MJPEGStreamDescriptor()

    @thing_action
    def snap_image(self) -> NDArray:
        """Acquire one image from the camera.

        This action cannot run if the camera is in use by a background thread, for
        example if a preview stream is running.
        """
        return self.capture_array()

    @thing_action
    def grab_jpeg(
        self,
        portal: BlockingPortal,
        stream_name: Literal["main", "lores"] = "main",
    ) -> JPEGBlob:
        """Acquire one image from the preview stream and return as an array

        This differs from `capture_jpeg` in that it does not pause the MJPEG
        preview stream. Instead, we simply return the next frame from that
        stream (either "main" for the preview stream, or "lores" for the low
        resolution preview). No metadata is returned.
        """
        logging.info(
            f"StreamingPiCamera2.grab_jpeg(stream_name={stream_name}) starting"
        )
        stream = (
            self.lores_mjpeg_stream if stream_name == "lores" else self.mjpeg_stream
        )
        frame = portal.call(stream.grab_frame)
        logging.info(
            f"StreamingPiCamera2.grab_jpeg(stream_name={stream_name}) got frame"
        )
        return JPEGBlob.from_bytes(frame)

    @thing_action
    def grab_jpeg_size(
        self,
        portal: BlockingPortal,
        stream_name: Literal["main", "lores"] = "main",
    ) -> int:
        """Acquire one image from the preview stream and return its size"""
        stream = (
            self.lores_mjpeg_stream if stream_name == "lores" else self.mjpeg_stream
        )
        return portal.call(stream.next_frame_size)


class CameraStub(BaseCamera):
    """A stub for a camera, to allow dependencies


    As of LabThings-FastAPI 0.0.7, we can't make a thing client dependency
    based on a protocol, because the protocol is not a Thing, and its
    methods/properties are not decorated as Affordances. This stub class
    is a workaround for that limitation, and should not be used directly.

    This stub class should be used for dependencies on the CameraProtocol.
    """

    def __enter__(self) -> None:
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    @thing_property
    def stream_active(self) -> bool:
        "Whether the MJPEG stream is active"
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    @thing_action
    def snap_image(self) -> NDArray:
        """Acquire one image from the camera."""
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
    def start_streaming(self, main_resolution) -> None:
        """Start (or stop and restart) the camera with the given resolution
        for the main stream"""
        raise NotImplementedError("Cameras must not inherit from CameraStub")
    

CameraDependency = direct_thing_client_dependency(CameraStub, "/camera/")
RawCameraDependency = raw_thing_dependency(CameraProtocol)
