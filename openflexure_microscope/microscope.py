# -*- coding: utf-8 -*-
"""
Defines a microscope object, binding a camera and stage with basic functionality.
"""
import atexit
import logging
import time
import uuid
from typing import Dict, List, Optional, Tuple, Union

import pkg_resources
from expiringdict import ExpiringDict
from labthings import CompositeLock

from openflexure_microscope.camera.base import BaseCamera
from openflexure_microscope.camera.mock import MissingCamera
from openflexure_microscope.captures import THUMBNAIL_SIZE, CaptureManager
from openflexure_microscope.settings import OpenflexureSettingsFile
from openflexure_microscope.stage.base import BaseStage
from openflexure_microscope.stage.mock import MissingStage


class Microscope:
    """
    A basic microscope object.

    The camera and stage objects may already be initialised, and can be passed as arguments.
    """

    def __init__(
        self,
        camera: BaseCamera,
        stage: BaseStage,
        settings: OpenflexureSettingsFile,
        capture_manager: CaptureManager,
    ):
        self.id: str = f"openflexure:microscope:{uuid.uuid4()}"
        self.name: str = self.id

        self.captures: CaptureManager = capture_manager

        # Store settings and configuration files
        self.settings_file: OpenflexureSettingsFile = settings

        self.extension_settings: dict = {}

        # Attach hardware and check its type
        self.camera: BaseCamera = camera  #: Currently connected camera object
        if not isinstance(self.camera, BaseCamera):
            raise ValueError(
                "The microscope requires a camera that is a BaseCamera instance."
            )
        self.stage: BaseStage = stage  #: Currently connected stage object
        if not isinstance(self.stage, BaseStage):
            raise ValueError(
                "The microscope requires a stage that is a BaseStage instance."
            )

        # Ensure we lock the camera/stage when we lock the microscope
        self.lock: CompositeLock = CompositeLock([])
        if hasattr(self.camera, "lock"):
            self.lock.locks.append(self.camera.lock)
        if hasattr(self.stage, "lock"):
            self.lock.locks.append(self.stage.lock)

        # Apply settings loaded from file
        self.update_settings(self.settings_file.load())

        # Data cache
        # Sometimes, like when doing large scans, we don't need to read the hardware
        # state for every single capture. We can get the data once at the start,
        # cache it, and reuse that to save on IO. Cached data is stored here.
        self.configuration_cache: Union[dict, ExpiringDict] = ExpiringDict(
            max_len=100, max_age_seconds=3600
        )
        self.metadata_cache: Union[dict, ExpiringDict] = ExpiringDict(
            max_len=100, max_age_seconds=3600
        )
        atexit.register(self.handle_app_exit)

    def __enter__(self):
        """Create microscope on context enter."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close microscope on context exit."""
        self.close()

    def close(self):
        """Shut down the microscope hardware."""
        logging.info("Closing %s", (self))
        if self.camera:
            try:
                self.camera.close()
            except TimeoutError as e:
                logging.error(e)
        if self.stage:
            try:
                self.stage.close()
            except TimeoutError as e:
                logging.error(e)
        self.captures.close()
        # Once the hardware is closed, no need to close it again when we exit.
        atexit.unregister(self.handle_app_exit)
        logging.info("Closed %s", (self))

    def handle_app_exit(self):
        # Automatically clean up microscope at exit
        logging.debug("Microscope saving settings and shutting down hardware...")
        time.sleep(0.5)
        self.save_settings()
        time.sleep(0.5)
        self.close()
        logging.debug("Microscope shut down cleanly.")

    def has_real_stage(self) -> bool:
        """
        Check if a real (non-mock) stage is currently attached.
        """
        if hasattr(self, "stage") and not isinstance(self.stage, MissingStage):
            return True
        else:
            return False

    def has_real_camera(self) -> bool:
        """
        Check if a real (non-mock) camera is currently attached.
        """
        if hasattr(self, "camera") and not isinstance(self.camera, MissingCamera):
            return True
        else:
            return False

    # Create unified state
    @property
    def state(self) -> dict:
        """Dictionary of the basic microscope state.

        Return:
            dict: Dictionary containing complete microscope state
        """
        return {"camera": self.camera.state, "stage": self.stage.state}

    def update_settings(self, settings: dict):
        """
        Applies a settings dictionary to the microscope. Missing parameters will be left untouched.
        """
        with self.lock:
            logging.debug("Microscope: Applying settings: %s", (settings))

            # If attached to a camera
            if ("camera" in settings) and self.camera:
                self.camera.update_settings(settings.pop("camera", {}))

            # If attached to a stage
            if ("stage" in settings) and self.stage:
                self.stage.update_settings(settings.pop("stage", {}))

            # Capture manager
            self.captures.update_settings(settings.pop("captures", {}))

            # Microscope settings
            if "id" in settings:
                self.id = settings.pop("id")
            if "name" in settings:
                self.name = settings.pop("name")

            # Extension settings
            if "extensions" in settings:
                self.extension_settings.update(settings.pop("extensions"))

            # Warn about any superfluous keys
            for key in settings.keys():
                logging.warning("Key %s is unused and was ignored", key)

    def read_settings(self, full: bool = True) -> dict:
        """
        Get an updated settings dictionary.

        Reads current attributes and properties from connected hardware,
        then merges those with the currently saved settings.

        This is to ensure that settings for currently disconnected hardware
        don't get removed from the settings file.
        """
        settings_current = {
            "id": self.id,
            "name": self.name,
            "extensions": self.extension_settings,
        }

        # If attached to a camera
        if self.camera:
            settings_current_camera = self.camera.read_settings()
            settings_current["camera"] = settings_current_camera

        # If attached to a stage
        if self.stage:
            settings_current_stage = self.stage.read_settings()
            settings_current["stage"] = settings_current_stage

        # Capture manager
        settings_current_captures = self.captures.read_settings()
        settings_current["captures"] = settings_current_captures

        settings_full = self.settings_file.merge(settings_current)

        if full:
            return settings_full
        else:
            return settings_current

    def save_settings(self):
        """
        Merges the current settings back to disk
        """
        # Read curent config
        current_config = self.read_settings()
        # Save config to file
        self.settings_file.save(current_config, backup=True)

    def force_get_configuration(self) -> dict:
        initial_configuration = self.configuration_file.load()

        current_configuration = {
            "application": {
                "name": "openflexure-microscope-server",
                "version": pkg_resources.get_distribution(
                    "openflexure-microscope-server"
                ).version,
            },
            "stage": {
                "type": self.stage.__class__.__name__,
                **self.stage.configuration,
            },
            "camera": {
                "type": self.camera.__class__.__name__,
                **self.camera.configuration,
            },
        }

        initial_configuration.update(current_configuration)
        return initial_configuration

    def get_configuration(self, cache_key: Optional[str] = None) -> dict:
        if cache_key:
            cached_config = self.configuration_cache.get(cache_key, None)
            if cached_config:
                return cached_config
            else:
                full_config = self.force_get_configuration()
                self.configuration_cache[cache_key] = full_config
                return full_config
        return self.force_get_configuration()

    @property
    def configuration(self):
        return self.get_configuration()

    def force_get_metadata(self) -> dict:
        """
        Read cachable bits of microscope metadata.
        Currently ID, settings, and configuration can be cached
        """
        system_metadata = {
            "id": self.id,
            "settings": self.read_settings(full=False),
            "configuration": self.get_configuration(),
        }

        return system_metadata

    def get_metadata(self, cache_key: Optional[str] = None):
        """
        Read microscope metadata, with partial caching
        """
        metadata = {}

        # Load cached bits of metadata
        if cache_key:
            logging.debug("Reading cached microscope metadata: %s", cache_key)
            metadata = self.metadata_cache.get(cache_key, None)
            if not metadata:
                logging.debug("Building and caching microscope metadata: %s", cache_key)
                metadata = self.force_get_metadata()
                self.metadata_cache[cache_key] = metadata
        else:
            logging.debug("Building microscope metadata: %s", cache_key)
            metadata = self.force_get_metadata()

        # Keys that should never be cached
        metadata.update({"state": self.state})

        return metadata

    @property
    def metadata(self) -> dict:
        return self.get_metadata()

    def capture(
        self,
        filename: Optional[str] = None,
        folder: str = "",
        temporary: bool = False,
        use_video_port: bool = False,
        resize: Tuple[int, int] = None,
        bayer: bool = True,
        fmt: str = "jpeg",
        annotations: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        dataset: Optional[Dict[str, str]] = None,
        metadata: Optional[dict] = None,
        cache_key: Optional[str] = None,
    ):
        logging.debug("Microscope capturing to %s", filename)
        if not annotations:
            annotations = {}
        if not metadata:
            metadata = {}
        if not tags:
            tags = []

        # Read metadata for capture
        full_metadata = {"instrument": self.get_metadata(cache_key), **metadata}

        # Do capture
        with self.camera.lock:
            # Create output object
            output = self.captures.new_image(
                temporary=temporary, filename=filename, folder=folder, fmt=fmt
            )

            # Capture to output object
            logging.info("Starting microscope capture %s", output.file)
            self.camera.capture(
                output,
                use_video_port=use_video_port,
                resize=resize,
                bayer=bayer,
                fmt=fmt,
                thumbnail=(*THUMBNAIL_SIZE, 85),
            )

        output.put_and_save(tags, annotations, dataset, full_metadata)
        logging.debug("Finished capture to %s", output.file)

        return output
