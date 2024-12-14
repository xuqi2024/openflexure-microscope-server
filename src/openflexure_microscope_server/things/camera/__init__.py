"""OpenFlexure Microscope Camera

This module defines the interface for cameras. Any compatible Thing
should enabe the server to work.

See repository root for licensing information.
"""

from __future__ import annotations
import logging
from typing import Any, Literal, Protocol, runtime_checkable

from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.dependencies.blocking_portal import BlockingPortal
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.raw_thing import raw_thing_dependency
from labthings_fastapi.outputs.mjpeg_stream import MJPEGStreamDescriptor
from labthings_fastapi.outputs.blob import Blob
from labthings_fastapi.types.numpy import NDArray
import numpy as np
from PIL import Image
import io


class JPEGBlob(Blob):
    media_type: str = "image/jpeg"


class PNGBlob(Blob):
    media_type: str = "image/png"


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
        resolution: Literal["lores", "main", "full"] = "main",
    ) -> NDArray: ...

    def capture_raw(
        self,
        get_states: bool = True,
        get_processing_inputs: bool = True,
    ) -> Any: ...

    def raw_to_png(
        self,
        raw: Any,
        use_cache: bool = False,
    ) -> PNGBlob: ...

    def capture_jpeg(
        self,
        metadata_getter: GetThingStates,
        resolution: Literal["lores", "main", "full"] = "main",
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


class RawIsArrayCamera:
    """A mixin for cameras that use arrays as their raw format"""

    @thing_action
    def capture_raw(
        self,
        get_states: bool = True,  # noqa: unused-argument
        get_processing_inputs: bool = True,  # noqa: unused-argument
    ) -> NDArray:
        return self.capture_array()

    @thing_action
    def raw_to_png(
        self,
        raw: NDArray,
    ) -> PNGBlob:
        image = Image.fromarray(raw.astype(np.uint8), mode="RGB")
        out = io.BytesIO()
        image.save(out, format="png")
        return PNGBlob.from_bytes(out.getvalue())


class CameraStub(BaseCamera, RawIsArrayCamera):
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
        resolution: Literal["lores", "main", "full"] = "main",
    ) -> NDArray:
        raise NotImplementedError("Cameras must not inherit from CameraStub")

    @thing_action
    def capture_jpeg(
        self,
        metadata_getter: GetThingStates,
        resolution: Literal["lores", "main", "full"] = "main",
    ) -> JPEGBlob:
        """Acquire one image from the camera and return as a JPEG blob"""
        raise NotImplementedError("Cameras must not inherit from CameraStub")


CameraDependency = direct_thing_client_dependency(CameraStub, "/camera/")
RawCameraDependency = raw_thing_dependency(CameraProtocol)
