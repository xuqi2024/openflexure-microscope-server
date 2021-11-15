# -*- coding: utf-8 -*-
"""
Defines a microscope object, binding a camera and stage with basic functionality.
"""
from json import load
import logging
import uuid
from typing import Dict, List, Optional, Tuple, Union

import pkg_resources

from expiringdict import ExpiringDict

from openflexure_microscope.camera.base import BaseCamera
from openflexure_microscope.camera.mock import MissingCamera
from openflexure_microscope.captures import THUMBNAIL_SIZE, CaptureManager
from openflexure_microscope.config import OpenflexureSettingsFile
from openflexure_microscope.stage.base import BaseStage
from openflexure_microscope.stage.mock import MissingStage
from openflexure_microscope.utilities import load_entrypoint

try:
    from openflexure_microscope.camera.pi import PiCameraStreamer
except Exception as exc:  # pylint: disable=W0703
    logging.error(exc)
    logging.warning("Unable to import PiCameraStreamer")
from labthings import CompositeLock

from openflexure_microscope.config import user_configuration, user_settings


class Microscope:
    """
    A basic microscope object.

    The camera and stage objects may already be initialised, and can be passed as arguments.
    """

    def __init__(self, settings=user_settings, configuration=user_configuration):
        self.id: str = f"openflexure:microscope:{uuid.uuid4()}"
        self.name: str = self.id

        self.captures: CaptureManager = CaptureManager()

        # Store settings and configuration files
        self.settings_file: OpenflexureSettingsFile = settings
        self.configuration_file: OpenflexureSettingsFile = configuration

        self.extension_settings: dict = {}

        # Initialise with an empty composite lock
        #: :py:class:`labthings.CompositeLock`: Composite lock for locking both camera and stage
        self.lock: CompositeLock = CompositeLock([])

        self.camera: BaseCamera = None  #: Currently connected camera object
        self.stage: BaseStage = None  #: Currently connected stage object

        self.setup(self.configuration_file.load())  # Attach components

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
        logging.info("Closed %s", (self))

    def setup(self, configuration: dict):
        """
        Attach microscope components based on initially passed configuration file
        """

        ### Detector
        logging.info("Creating camera")
        if configuration.get("camera"):
            camera_type = configuration["camera"].get("type")
            if camera_type in ("PiCamera", "PiCameraStreamer"):
                try:
                    self.camera = PiCameraStreamer()
                except Exception as e:  # pylint: disable=W0703
                    logging.error(e)
                    logging.warning("No compatible camera hardware found.")

        ### Stage
        self.set_stage(configuration=configuration)

        logging.info("Handling fallbacks")
        ### Fallbacks
        if not self.camera:
            self.camera = MissingCamera()
        if not self.stage:
            self.stage = MissingStage()

        ### Locks
        logging.info("Creating locks")
        if hasattr(self.camera, "lock"):
            self.lock.locks.append(self.camera.lock)
        if hasattr(self.stage, "lock"):
            self.lock.locks.append(self.stage.lock)

    def set_stage(
        self, configuration: Optional[dict] = None, stage_type: Optional[str] = None
    ):
        """
        Set or change the stage geometry
        """
        configuration = configuration or self.configuration

        if stage_type:
            if stage_type == configuration["stage"].get("type"):
                logging.info("Stage already set to that stage type")
                return
        else:
            stage_type = configuration["stage"].get("type")

        ### Close any existing stages
        if self.stage:
            self.stage.close()

        logging.info("Setting stage")
        stage_port = configuration["stage"].get("port")

        stage_class = load_entrypoint(stage_type, "openflexure_microscope_stages")

        logging.info(f"Attempting to instantiate stage '{stage_type}'")
        self.stage = stage_class(port=stage_port)
        configuration["stage"]["type"] = stage_type
        self.configuration_file.save(configuration)


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
