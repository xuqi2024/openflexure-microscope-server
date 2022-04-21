import datetime
import logging
import os
import shutil
from collections import OrderedDict
from typing import Dict, List, MutableMapping, Optional, Union, ValuesView
from uuid import UUID

from labthings import StrictLock

from .capture import CaptureObject, build_captures_from_exif


class CaptureManager:
    def __init__(self, default_data_path: str):
        self.paths: Dict[str, str] = {
            "default": default_data_path,
            "temp": os.path.join(default_data_path, "tmp"),
        }

        self.lock: StrictLock = StrictLock(timeout=1, name="Captures")

        # Capture data
        self.images: MutableMapping[str, CaptureObject] = OrderedDict()
        self.videos: MutableMapping[str, CaptureObject] = OrderedDict()

    # FILE MANAGEMENT

    def __enter__(self):
        """Create camera on context enter."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close camera stream on context exit."""
        self.close()

    def close(self):
        logging.info("Closing %s", (self))
        # Close all StreamObjects
        for capture_list in [self.images.values(), self.videos.values()]:
            for stream_object in capture_list:
                stream_object.close()
        # Empty temp directory
        self.clear_tmp()

    def clear_tmp(self):
        """
        Removes all files in the temporary capture directories
        """

        if os.path.isdir(self.paths["temp"]):
            logging.info("Clearing %s...", (self.paths["temp"]))
            shutil.rmtree(self.paths["temp"])
            logging.debug("Cleared %s.", (self.paths["temp"]))

    def rebuild_captures(self):
        self.images = build_captures_from_exif(self.paths["default"])

    def update_settings(self, config: dict):
        """Update settings from a config dictionary"""
        with self.lock:
            # Apply valid config params to camera object
            for key, value in config.items():  # For each provided setting
                if hasattr(self, key):  # If the instance has a matching property
                    setattr(self, key, value)  # Set to the target value

    def read_settings(self) -> dict:
        """Return the current settings as a dictionary"""
        return {"paths": self.paths}

    # RETURNING CAPTURES

    def image_from_id(self, image_id: Union[str, int, UUID]) -> Optional[CaptureObject]:
        """Return an image StreamObject with a matching ID."""
        logging.warning("image_from_id is deprecated. Access captures as a dictionary.")
        return entry_by_uuid(image_id, self.images)

    def video_from_id(self, video_id: Union[str, int, UUID]) -> Optional[CaptureObject]:
        """Return a video StreamObject with a matching ID."""
        logging.warning("video_from_id is deprecated. Access captures as a dictionary.")
        return entry_by_uuid(video_id, self.videos)

    # CREATING NEW CAPTURES

    def _new_output(self, temporary: bool, filename: str, folder: str, fmt: str):

        filename = "{}.{}".format(filename, fmt)

        # Generate folder
        base_folder: str = self.paths["temp"] if temporary else self.paths["default"]
        folder = os.path.join(base_folder, folder)

        # Generate file path
        filepath: str = os.path.join(folder, filename)

        # Create capture object
        output = CaptureObject(filepath=filepath)
        # Insert a temporary tag if temporary
        if temporary:
            output.put_tags(["temporary"])

        return output

    def new_image(
        self,
        temporary: bool = True,
        filename: Optional[str] = None,
        folder: str = "",
        fmt: str = "jpeg",
    ):

        """
        Create a new image capture object.

        Args:
            temporary (bool): Should the data be deleted after session ends. 
                Creating the capture with a content manager sets this to true.
            filename (str): Name of the stored file. Defaults to timestamp.
            folder (str): Name of the folder in which to store the capture.
            fmt (str): Format of the capture.
        """
        # Generate file name
        if not filename:
            filename = generate_numbered_basename(self.images.values())

        # Create a new output object
        output = self._new_output(temporary, filename, folder, fmt)
        # Add an on-delete callback
        output.on_delete = self.remove_image

        # Update capture list
        logging.debug("Adding image %s with key %s", output, output.id)
        self.images[str(output.id)] = output

        return output

    def new_video(
        self,
        temporary: bool = False,
        filename: Optional[str] = None,
        folder: str = "",
        fmt: str = "h264",
    ) -> CaptureObject:

        """
        Create a new video capture object.

        Args:
            temporary (bool): Should the data be deleted after session ends. 
                Creating the capture with a content manager sets this to true.
            filename (str): Name of the stored file. Defaults to timestamp.
            folder (str): Name of the folder in which to store the capture.
            fmt (str): Format of the capture.
        """
        # Generate file name
        if not filename:
            filename = generate_numbered_basename(self.videos.values())

        # Create a new output object
        output = self._new_output(temporary, filename, folder, fmt)
        # Add an on-delete callback
        output.on_delete = self.remove_video

        # Update capture list
        logging.debug("Adding video %s with key %s", output, output.id)
        self.videos[str(output.id)] = output

        return output

    def remove_image(self, capture_obj: CaptureObject, capture_id: str):
        logging.info("Deleting capture %s", capture_id)
        if capture_id in self.images:
            logging.info("Deleting capture object %s", capture_obj)
            del self.images[capture_id]

    def remove_video(self, capture_obj: CaptureObject, capture_id: str):
        logging.info("Deleting capture %s", capture_id)
        if capture_id in self.images:
            logging.info("Deleting capture object %s", capture_obj)
            del self.videos[capture_id]


def entry_by_uuid(
    entry_id: Union[str, int, UUID], object_dict: MutableMapping[str, CaptureObject]
) -> Optional[CaptureObject]:
    """Return an object from a list, if <object>.id matches id argument."""
    if isinstance(entry_id, str):
        key: str = entry_id
    elif isinstance(entry_id, UUID):
        key = str(entry_id)
    elif isinstance(entry_id, int):
        key = str(UUID(int=entry_id))
    else:
        raise TypeError("Argument entry_id must be a string, integer, or UUID object.")

    return object_dict.get(key)


def generate_basename() -> str:
    """Return a default filename based on the capture datetime"""
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def generate_numbered_basename(
    obj_list: Union[ValuesView[CaptureObject], List[CaptureObject]]
) -> str:
    """
    This function prevents rapid captures from having clashing generated names.

    Our generated names are a datetime string going as far as seconds,
    so if you create 2 captures within 1 second then they would have a name
    clash. This method handles appending sequential integers to names
    that would clash.
    """
    initial_basename = generate_basename()
    basename = initial_basename
    # Handle clashing
    iterator = 1
    while basename in [obj.basename for obj in obj_list]:
        basename = initial_basename + "_{}".format(iterator)
        iterator += 1

    return basename
