from typing import Literal
from pydantic import RootModel

from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action
from labthings_fastapi.descriptors import PropertyDescriptor
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.outputs.mjpeg_stream import MJPEGStreamDescriptor
from labthings_fastapi.outputs import NDArray
from labthings_fastapi.outputs.blob import BlobOutput


class ArrayModel(RootModel):
    root: NDArray


class JPEGBlob(BlobOutput):
    media_type = "image/jpeg"


class AbstractCamera(Thing):
    stream_active = PropertyDescriptor(
        bool,
        description="Whether the MJPEG stream is active",
        observable=True,
        readonly=True,
    )
    mjpeg_stream = MJPEGStreamDescriptor()
    lores_mjpeg_stream = MJPEGStreamDescriptor()

    @thing_action
    def capture_array(
        self, stream_name: Literal["main", "lores", "raw"] = "main"
    ) -> ArrayModel:
        """Acquire one image from the camera and return as an array

        This function will produce a nested list containing an uncompressed RGB image.
        It's likely to be highly inefficient - raw and/or uncompressed captures using
        binary image formats will be added in due course.
        """
        _ = stream_name
        raise NotImplementedError
    
    @thing_action
    def capture_jpeg(
        self,
        metadata_getter: GetThingStates,
        resolution: Literal["lores", "main", "full"] = "main",
    ) -> JPEGBlob:
        """Acquire one image from the camera as a JPEG"""
        _ = metadata_getter
        _ = resolution
        raise NotImplementedError
