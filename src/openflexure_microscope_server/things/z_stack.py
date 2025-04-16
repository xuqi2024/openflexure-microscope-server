import os
import numpy as np
from PIL import Image
import time
import piexif
import json
import shutil
import glob

from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from .camera import CameraDependency as CamDep
from .stage import StageDependency as StageDep
from labthings_fastapi.dependencies.invocation import (
    InvocationLogger,
)


class CaptureError(RuntimeError):
    """An error trying to capture from Picamera"""


class ZStackThing(Thing):
    @thing_property
    def images_to_capture(self) -> int:
        """The number of images to capture and save in a stack
        Defaults to 1 unless you need to see either side of focus"""
        return self.thing_settings.get("images_to_capture", 1)

    @images_to_capture.setter
    def images_to_capture(self, value: int) -> None:
        self.thing_settings["images_to_capture"] = value

    @thing_property
    def stack_dz(self) -> int:
        """Space in steps between images in a z-stack
        Suggested is 50 for 60-100x
        100 for 40x
        200 for 20x"""
        return self.thing_settings.get("stack_dz", 50)

    @stack_dz.setter
    def stack_dz(self, value: int) -> None:
        self.thing_settings["stack_dz"] = value

    @thing_action
    def smart_stack(
        self,
        cam: CamDep,
        stage: StageDep,
        logger: InvocationLogger,
        metadata_getter: GetThingStates,
        images_dir: str,
        stack_dir: str,
    ) -> None:
        stack_dz = self.stack_dz
        images_to_capture = self.images_to_capture

        stack_z_range = stack_dz * (images_to_capture - 1)
        stage.move_relative(z=-stack_z_range / 2)

        for capture_count in range(images_to_capture):
            jpeg_path = os.path.join(
                stack_dir,
                f"{capture_count}.jpeg",
            )
            self._capture_and_save(
                jpeg_path=jpeg_path,
                cam=cam,
                logger=logger,
                metadata_getter=metadata_getter,
            )
            stage.move_relative(z=stack_dz)
            time.sleep(0.3)

        self.copy_central_image(images_dir, stack_dir, logger)

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
        )
        acquisition_time = time.time()
        self._save_capture(jpeg_path, image, metadata, logger)
        save_time = time.time()
        acquisition_duration = round(acquisition_time - capture_start, 1)
        saving_duration = round(save_time - acquisition_time, 1)
        logger.info(
            f"Acquired {jpeg_path} in {acquisition_duration}s then {saving_duration}s saving to disk"
        )

    def _capture_image(self, cam, metadata_getter) -> tuple[np.ndarray, dict]:
        """Capture an image in memory and return it with metadata
        CaptureError raised if the capture fails for any reason
        returns tuple with numpy array of image data, and dict of metadata
        """
        try:
            metadata = metadata_getter()
            image = cam.capture_array()[..., :3]
        except Exception as e:
            raise CaptureError("An error occurred while capturing") from e
        return image, metadata

    def _save_capture(
        self,
        jpeg_path: str,
        image: np.ndarray,
        metadata: dict,
        logger: InvocationLogger,
    ) -> None:
        """Saving the captured image and metadata to disk
        logger warning (via InvocationLogger) is raised if metadata is failed to be added
        IOError is raised if the file cannot be saved
        nothing is returned on success"""
        try:
            Image.fromarray(image.astype("uint8"), "RGB").save(
                jpeg_path, quality=95, subsampling=0
            )
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

    def copy_central_image(
        self,
        images_dir: str,
        stack_dir: str,
        logger: InvocationLogger,
    ):
        """Gets a list of images in a folder (stack_dir), sorts them, and copies the central image
        to images dir."""
        image_list = glob.glob(os.path.join(stack_dir, "*"))
        image_list.sort()
        central_index = (len(image_list) - 1) // 2
        central_image = image_list[central_index]
        logger.warning(central_image)
        xy_location = os.path.basename(stack_dir)

        shutil.copy(central_image, os.path.join(images_dir, f"{xy_location}.jpeg"))
