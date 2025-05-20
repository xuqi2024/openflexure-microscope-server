import time
import piexif
import json

from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action
from .camera import CameraDependency as CamDep
from labthings_fastapi.dependencies.invocation import (
    InvocationLogger,
)


class CaptureError(RuntimeError):
    """An error trying to capture from Picamera"""


class CaptureThing(Thing):
    """A temporary Thing to handle capturing to disk with associated metadata
    Will be moved to the camera Thing or dependency in due course"""

    @thing_action
    def _capture_and_save(
        self,
        jpeg_path: str,
        cam: CamDep,
        logger: InvocationLogger,
        metadata_getter: GetThingStates,
    ) -> None:
        """Capture an image and save it to disk

        This will set the event `acquired` once the image has been acquired, so
        that the stage may be moved while it's saved.
        """
        capture_start = time.time()
        image, metadata = self._capture_image(
            cam,
            metadata_getter,
            logger=logger,
        )
        acquisition_time = time.time()
        self._save_capture(
            jpeg_path,
            image,
            metadata,
            logger,
        )
        save_time = time.time()
        acquisition_duration = round(acquisition_time - capture_start, 1)
        saving_duration = round(save_time - acquisition_time, 1)
        logger.info(
            f"Acquired {jpeg_path} in {acquisition_duration}s then {saving_duration}s saving to disk"
        )

    @thing_action
    def _capture_image(
        self,
        cam: CamDep,
        metadata_getter: GetThingStates,
        logger: InvocationLogger,
    ):
        """Capture an image in memory and return it with metadata
        CaptureError raised if the capture fails for any reason
        returns tuple with PIL Image, and dict of metadata
        """
        for capture_attempts in range(5):
            try:
                metadata = metadata_getter()
                image = cam.capture_image(stream_name="main", wait=5)
                return image, metadata
            except TimeoutError:
                logger.warning(
                    f"Attempt {capture_attempts + 1} to capture image timed out. Do you have enough RAM?"
                )
        raise CaptureError("An error occurred while capturing after 5 attempts")

    @thing_action
    def _save_capture(
        self,
        jpeg_path: str,
        image,
        metadata: dict,
        logger: InvocationLogger,
    ) -> None:
        """Saving the captured image and metadata to disk
        logger warning (via InvocationLogger) is raised if metadata is failed to be added
        IOError is raised if the file cannot be saved
        nothing is returned on success"""
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
