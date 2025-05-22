"""OpenFlexure Microscope Camera

This module defines the interface for cameras. Any compatible Thing
should enabe the server to work.

See repository root for licensing information.
"""

from __future__ import annotations
from typing import Literal, Optional, Tuple
import json

from pydantic import RootModel
from PIL import Image
import piexif

from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.dependencies.blocking_portal import BlockingPortal
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.raw_thing import raw_thing_dependency
from labthings_fastapi.dependencies.invocation import InvocationLogger
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


class CaptureError(RuntimeError):
    """An error trying to capture from a CameraThing"""


class NoImageInMemoryError(RuntimeError):
    """An error called if no image in in memory when an method is called to use that image"""


class BaseCamera(Thing):
    """The base class for all cameras. All cameras must directly inherit from this class"""

    _memory_image: Optional[Image] = None
    _memory_metadata: Optional[dict] = None
    mjpeg_stream = MJPEGStreamDescriptor()
    lores_mjpeg_stream = MJPEGStreamDescriptor()

    def __enter__(self) -> None:
        raise NotImplementedError("CameraThings must define their own __enter__ method")

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        raise NotImplementedError("CameraThings must define their own __exit__ method")

    @thing_property
    def image_in_memory(self) -> bool:
        """True if an image is in memory ready to be saved"""
        return self._memory_image is not None and self._memory_metadata is not None

    @thing_action
    def clear_image_memory(self) -> None:
        """Clear any image in memory"""
        self._memory_image = None
        self._memory_metadata = None

    @thing_action
    def start_streaming(self, main_resolution, buffer_count) -> None:
        """Start (or stop and restart) the camera with the given resolution
        for the main stream, and buffer_count number of images in the buffer"""
        raise NotImplementedError(
            "CameraThings must define their own start_streaming method"
        )

    @thing_property
    def stream_active(self) -> bool:
        "Whether the MJPEG stream is active"
        raise NotImplementedError(
            "CameraThings must define their own stream_active method"
        )

    @thing_action
    def capture_array(
        self,
        stream_name: Literal["main", "lores", "raw", "full"] = "main",
        wait: Optional[float] = 5,
    ) -> NDArray:
        raise NotImplementedError(
            "CameraThings must define their own capture_array method"
        )

    @thing_action
    def capture_jpeg(
        self,
        metadata_getter: GetThingStates,
        resolution: Literal["lores", "main", "full"] = "main",
        wait: Optional[float] = 5,
    ) -> JPEGBlob:
        """Acquire one image from the camera and return as a JPEG blob"""
        raise NotImplementedError(
            "CameraThings must define their own capture_jpeg method"
        )

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
        stream = (
            self.lores_mjpeg_stream if stream_name == "lores" else self.mjpeg_stream
        )
        frame = portal.call(stream.grab_frame)
        return JPEGBlob.from_bytes(frame)

    @thing_action
    def capture_image(self, stream_name, wait):
        """Capture a PIL image from stream stream_name with timeout wait"""
        raise NotImplementedError(
            "CameraThings must define their own capture_image method"
        )

    @thing_action
    def capture_and_save(
        self,
        jpeg_path: str,
        logger: InvocationLogger,
        metadata_getter: GetThingStates,
        save_resolution: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Capture an image and save it to disk

        This will set the event `acquired` once the image has been acquired, so
        that the stage may be moved while it's saved.

        save_resolution can be set to resize the image before saving. By default this is None
            meaning that the image is saved at original resoltion.
        """
        image, metadata = self._robust_image_capture(
            metadata_getter,
            logger=logger,
        )

        self._save_capture(
            jpeg_path,
            image,
            metadata,
            logger,
            save_resolution,
        )

    @thing_action
    def capture_to_memory(
        self,
        logger: InvocationLogger,
        metadata_getter: GetThingStates,
    ) -> None:
        """
        Capture an image to memory. This can be saved later with `save_from_memory`

        Note that only one image is held in memory so this will overwrite any image
        in memory.
        """
        self._memory_image, self._memory_metadata = self._robust_image_capture(
            metadata_getter,
            logger=logger,
        )

    @thing_action
    def save_from_memory(
        self,
        jpeg_path: str,
        logger: InvocationLogger,
        save_resolution: Optional[Tuple[int, int]] = None,
    ) -> None:
        """
        Save an image that has been captured to memory.
        """
        if not self.image_in_memory:
            raise NoImageInMemoryError("No image in memory to save.")

        self._save_capture(
            jpeg_path=jpeg_path,
            image=self._memory_image,
            metadata=self._memory_metadata,
            logger=logger,
            save_resolution=save_resolution,
        )
        self.clear_image_memory()

    def _robust_image_capture(
        self,
        metadata_getter: GetThingStates,
        logger: InvocationLogger,
    ) -> Image:
        """Capture an image in memory and return it with metadata
        CaptureError raised if the capture fails for any reason
        returns tuple with PIL Image, and dict of metadata
        """
        for capture_attempts in range(5):
            try:
                metadata = metadata_getter()
                image = self.capture_image(stream_name="main", wait=5)
                return image, metadata
            except TimeoutError:
                logger.warning(
                    f"Attempt {capture_attempts + 1} to capture image timed out. Do you have enough RAM?"
                )
        raise CaptureError("An error occurred while capturing after 5 attempts")

    def _save_capture(
        self,
        jpeg_path: str,
        image: Image,
        metadata: dict,
        logger: InvocationLogger,
        save_resolution: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Saving the captured image and metadata to disk
        logger warning (via InvocationLogger) is raised if metadata is failed to be added
        IOError is raised if the file cannot be saved
        nothing is returned on success"""
        if save_resolution is not None and image.size != save_resolution:
            image = image.resize(save_resolution, Image.BOX)
        try:
            image.save(jpeg_path, quality=95, subsampling=0)
            try:
                exif_dict = piexif.load(jpeg_path)
                exif_dict["Exif"][piexif.ExifIFD.UserComment] = json.dumps(
                    metadata
                ).encode("utf-8")
                piexif.insert(piexif.dump(exif_dict), jpeg_path)
            except:  # noqa: E722
                # We need to capture any exception as there are many reasons metadata
                # might not be added. We warn rather than log the error.
                logger.warning(f"Failed to add metadata to {jpeg_path}")
        except Exception as e:
            raise IOError(f"An error occurred while saving {jpeg_path}") from e


CameraDependency = direct_thing_client_dependency(BaseCamera, "/camera/")
RawCameraDependency = raw_thing_dependency(BaseCamera)
