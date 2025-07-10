"""OpenFlexure Microscope Camera.

This module defines the interface for cameras. Any compatible lt.Thing
should enable the server to work.

See repository root for licensing information.
"""

from __future__ import annotations
from typing import Literal, Optional, Tuple, Any
import json

from pydantic import RootModel
from PIL import Image
import piexif

import labthings_fastapi as lt
from labthings_fastapi.types.numpy import NDArray


class JPEGBlob(lt.blob.Blob):
    """A class representing a JPEG image as a LabThings FastAPI Blob."""

    media_type: str = "image/jpeg"


class PNGBlob(lt.blob.Blob):
    """A class representing a PNG image as a LabThings FastAPI Blob."""

    media_type: str = "image/png"


class ArrayModel(RootModel):
    """A model for an array."""

    root: NDArray


class CaptureError(RuntimeError):
    """An error trying to capture from a CameraThing."""


class NoImageInMemoryError(RuntimeError):
    """An error called if no image is in memory when accessed."""


class CameraMemoryBuffer:
    """A class that holds images in memory. The images are by default PIL images.

    However subclasses of BaseCamera can use this class to store other object types.
    """

    _storage: dict[int, tuple[Any, Optional[dict]]]

    def __init__(self):
        """Create the buffer instance."""
        # This dictionary is the main store for data. Dictionaries are ordered since
        # Python 3.6, so the order in the dictionary is the capture order
        self._storage = {}
        # A simple id system where each capture id is just the number of captures since
        # the server starts
        self._latest_id: int = 0

    def add_image(
        self, image: Any, metadata: Optional[dict] = None, buffer_max: int = 1
    ) -> int:
        """Add an image to the Memory buffer.

        This will add an image to the memory buffer. By default the buffer will
        be cleared. To allow saving multiple images the buffer_max must be set
        every time an image is added.

        :param image: The image to add. A PIL image is recommended, but cameras
            can choose to use other formats
        :param metadata: Optional, a dictionary of the image metadata.
        :param buffer_max: The maximum number of images that should be in the buffer
            once this images is added. Default is 1.

        :returns: The id in the buffer for this image
        """
        self._latest_id += 1
        self._create_space(buffer_max)
        self._storage[self._latest_id] = (image, metadata)
        return self._latest_id

    def get_image(
        self, buffer_id: Optional[int] = None, remove: bool = True
    ) -> tuple[Any, Optional[dict]]:
        """Return the image with the given id.

        If no id is given the most recent image is returned. However, the
        buffer is also cleared, otherwise it would be possible to accidentally
        retrieve images out of order.

        :param buffer_id: The buffer id of the image to retrieve
        :param remove: True (default) to remove this image from the buffer, False
            to leave the image in the buffer.
        """
        # No id given
        if buffer_id is None:
            # Get the latest image and metadata tuple from storage
            try:
                image_tuple = list(self._storage.values())[-1]
            except IndexError as e:
                raise NoImageInMemoryError("No image in memory to retrieve.") from e
            # Clear the storage so images don't get retrieved out of order
            self._storage.clear()
            return image_tuple

        try:
            if remove:
                return self._storage.pop(buffer_id)
            return self._storage[buffer_id]
        except KeyError as e:
            raise NoImageInMemoryError(
                "No image with matching id in memory to retrieve."
            ) from e

    def clear(self):
        """Clear all images from memory."""
        self._storage.clear()

    def _create_space(self, buffer_max: int) -> None:
        """Create space to add an image.

        :param buffer_max: The maximum number of images that should be in the buffer
            once another images is added.
        """
        # If only one image to be stored just clear the storage and return
        if buffer_max <= 1:
            self._storage.clear()
            return

        # Number to remove to get the storage down to 1 less than the buffer length
        to_remove = len(self._storage) - (buffer_max - 1)
        # If if there is space. Nothing to do, just return
        if to_remove < 1:
            return

        keys_to_remove = list(self._storage.keys())[:to_remove]
        for key in keys_to_remove:
            del self._storage[key]


class BaseCamera(lt.Thing):
    """The base class for all cameras. All cameras must directly inherit from this class.

    The connection to the camera hardware should be added to the ``__enter__`` method not
    ``__init__`` method of the subclass.
    """

    mjpeg_stream = lt.outputs.MJPEGStreamDescriptor()
    lores_mjpeg_stream = lt.outputs.MJPEGStreamDescriptor()
    _memory_buffer = CameraMemoryBuffer()

    def __enter__(self) -> None:
        """Open hardware connection when the Thing context manager is opened."""
        raise NotImplementedError("CameraThings must define their own __enter__ method")

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        """Close hardware connection when the Thing context manager is closed."""
        raise NotImplementedError("CameraThings must define their own __exit__ method")

    @lt.thing_action
    def start_streaming(
        self, main_resolution: tuple[int, int], buffer_count: int
    ) -> None:
        """Start (or stop and restart) the camera.

        :param main_resolution: the resolution to use for the main stream.
        :param buffer_count: number of images in the stream buffer.
        """
        raise NotImplementedError(
            "CameraThings must define their own start_streaming method"
        )

    def kill_mjpeg_streams(self):
        """Kill the streams now as the server is shutting down.

        This is called when uvicorn gets the a shutdown signal. As this is called from
        the event loop it cannot interact with the our ThingProperties or run
        ``self.mjpeg_stream.stop()`` as the portal cannot be called from this loop.

        Instead we just set the ``_streaming`` value to False. This stops the async frame
        generator when the next frame notifies.
        """
        if self.stream_active:
            self.mjpeg_stream._streaming = False
            self.lores_mjpeg_stream._streaming = False

    @lt.thing_property
    def stream_active(self) -> bool:
        """Whether the MJPEG stream is active."""
        raise NotImplementedError(
            "CameraThings must define their own stream_active method"
        )

    @lt.thing_action
    def capture_array(
        self,
        stream_name: Literal["main", "lores", "raw", "full"] = "main",
        wait: Optional[float] = 5,
    ) -> NDArray:
        """Acquire one image from the camera and return as an array."""
        raise NotImplementedError(
            "CameraThings must define their own capture_array method"
        )

    @lt.thing_action
    def capture_jpeg(
        self,
        metadata_getter: lt.deps.GetThingStates,
        resolution: Literal["lores", "main", "full"] = "main",
        wait: Optional[float] = 5,
    ) -> JPEGBlob:
        """Acquire one image from the camera and return as a JPEG blob."""
        raise NotImplementedError(
            "CameraThings must define their own capture_jpeg method"
        )

    @lt.thing_action
    def grab_jpeg(
        self,
        portal: lt.deps.BlockingPortal,
        stream_name: Literal["main", "lores"] = "main",
    ) -> JPEGBlob:
        """Acquire one image from the preview stream and return as an array.

        This differs from ``capture_jpeg`` in that it does not pause the MJPEG
        preview stream. Instead, we simply return the next frame from that
        stream (either "main" for the preview stream, or "lores" for the low
        resolution preview). No metadata is returned.
        """
        stream = (
            self.lores_mjpeg_stream if stream_name == "lores" else self.mjpeg_stream
        )
        frame = portal.call(stream.grab_frame)
        return JPEGBlob.from_bytes(frame)

    @lt.thing_action
    def grab_jpeg_size(
        self,
        portal: lt.deps.BlockingPortal,
        stream_name: Literal["main", "lores"] = "main",
    ) -> int:
        """Acquire one image from the preview stream and return its size."""
        stream = (
            self.lores_mjpeg_stream if stream_name == "lores" else self.mjpeg_stream
        )
        return portal.call(stream.next_frame_size)

    @lt.thing_action
    def capture_image(
        self,
        stream_name: Literal["main", "lores", "raw"],
        wait: Optional[float],
    ) -> None:
        """Capture a PIL image from stream stream_name with timeout wait."""
        raise NotImplementedError(
            "CameraThings must define their own capture_image method"
        )

    @lt.thing_action
    def capture_and_save(
        self,
        jpeg_path: str,
        logger: lt.deps.InvocationLogger,
        metadata_getter: lt.deps.GetThingStates,
        save_resolution: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Capture an image and save it to disk.

        :param jpeg_path: The path to save the file to
        :param logger: This should be injected automatically by Labthings FastAPI
            when calling the action
        :param metadata_getter: This should be injected automatically by Labthings
            FastAPI when calling the action
        :param save_resolution: can be set to resize the image before saving. By
            default this is None meaning that the image is saved at original resolution.
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

    @lt.thing_action
    def capture_to_memory(
        self,
        logger: lt.deps.InvocationLogger,
        metadata_getter: lt.deps.GetThingStates,
        buffer_max: int = 1,
    ) -> None:
        """Capture an image to memory. This can be saved later with ``save_from_memory``.

        Note that only one image is held in memory so this will overwrite any image
        in memory.

        :param logger: This should be injected automatically by Labthings FastAPI
            when calling the action
        :param metadata_getter: This should be injected automatically by Labthings
            FastAPI when calling the action
        :param buffer_max: The maximum number of images that should be in the buffer
            once this images is added. Default is 1.

        :returns: the buffer id of the image captured
        """
        image, metadata = self._robust_image_capture(metadata_getter, logger)
        return self._memory_buffer.add_image(image, metadata, buffer_max=buffer_max)

    @lt.thing_action
    def save_from_memory(
        self,
        jpeg_path: str,
        logger: lt.deps.InvocationLogger,
        save_resolution: Optional[Tuple[int, int]] = None,
        buffer_id: Optional[int] = None,
    ) -> None:
        """Save an image that has been captured to memory.

        :param jpeg_path: The path to save the file to
        :param logger: This should be injected automatically by Labthings FastAPI
            when calling the action
        :param save_resolution: can be set to resize the image before saving. By
            default this is None meaning that the image is saved at original
            resolution.
        :param buffer_id: The buffer id of the image to save, this was returned by
            ``capture_to_memory``
        """
        image, metadata = self._memory_buffer.get_image(buffer_id)

        self._save_capture(
            jpeg_path=jpeg_path,
            image=image,
            metadata=metadata,
            logger=logger,
            save_resolution=save_resolution,
        )

    @lt.thing_action
    def clear_buffers(self) -> None:
        """Clear all images in memory."""
        self._memory_buffer.clear()

    def _robust_image_capture(
        self,
        metadata_getter: lt.deps.GetThingStates,
        logger: lt.deps.InvocationLogger,
    ) -> Image:
        """Capture an image in memory and return it with metadata.

        This robust capturing method attempts to capture the image five times
        each time with a 5 second timeout set.

        :raises CaptureError: if the capture fails for any reason

        :returns: tuple with PIL Image, and dictionary of metadata.
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
        logger: lt.deps.InvocationLogger,
        save_resolution: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Save the captured image and metadata to disk.

        A warning (via InvocationLogger) is raised if metadata is failed to be added

        :raises IOError: if the file cannot be saved

        nothing is returned on success
        """
        if save_resolution is not None and image.size != save_resolution:
            image = image.resize(save_resolution, Image.BOX)
        try:
            # Per PIL documentation,
            # (https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg)
            # there are two factors when saving a JPEG. Subsampling affects the colour,
            # quality affects the pixels.
            # subsampling = 0 disables subsampling of colour
            # quality = 95 is the maximum recommended - above this, JPEG compression is
            # disabled, file size increases and quality is barely or not affected
            image.save(jpeg_path, quality=95, subsampling=0)
            try:
                # Load EXIF metadata from image so it can be added to.
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


CameraDependency = lt.deps.direct_thing_client_dependency(BaseCamera, "/camera/")
RawCameraDependency = lt.deps.raw_thing_dependency(BaseCamera)
