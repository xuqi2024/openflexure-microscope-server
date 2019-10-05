# -*- coding: utf-8 -*-
"""
Defines a microscope object, binding a camera and stage with basic functionality.
"""
import logging
import pkg_resources
import uuid

from .stage.base import BaseStage

from .camera.base import BaseCamera

from .plugins import PluginMount
from .utilities import axes_to_array
from .task import TaskOrchestrator
from .lock import CompositeLock
from .config import OpenflexureSettingsFile, settings_to_json


class Microscope:
    """
    A basic microscope object.

    The camera and stage should already be initialised, and passed as arguments.

    Attributes:
        settings_file (:py:class:`openflexure_microscope.config.OpenflexureSettingsFile`): Runtime-config object,
            automatically created if None.
        lock (:py:class:`openflexure_microscope.lock.CompositeLock`): Composite lock controlling thread access
            to multiple pieces of hardware.
        camera (:py:class:`openflexure_microscope.camera.base.BaseCamera`): Camera object
        stage (:py:class:`openflexure_microscope.stage.base.BaseStage`): Stage object
        task: (:py:class:`openflexure_microscope.task.TaskOrchestrator`): Threaded ask orchestrator for managing
            background tasks using microscope hardware
        plugin (:py:class:`openflexure_microscope.plugins.PluginMount`): Mounting point for all microscope plugins
    """

    def __init__(self):
        # Initial attributes
        self.id = uuid.uuid4().hex
        self.name = self.id
        self.fov = [0, 0]
        self.plugin_maps = []
        self.camera = None
        self.stage = None

        # Initialise with an empty composite lock
        self.lock = CompositeLock([])

        # Create a task orchestrator
        self.task = TaskOrchestrator()

        # Attach to a settings file
        self.settings_file = OpenflexureSettingsFile(expand=True)
        # Apply settings loaded from file
        self.apply_config(self.settings_file.load())

        # Create plugin mount-point and attach plugins from maps
        self.plugin = PluginMount(self)
        self.attach_plugins(self.plugin_maps)

    def __enter__(self):
        """Create microscope on context enter."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close microscope on context exit."""
        self.close()

    def close(self):
        """Shut down the microscope hardware."""
        logging.info("Closing {}".format(self))
        if self.camera:
            self.camera.close()
        if self.stage:
            self.stage.close()
        logging.info("Closed {}".format(self))

    def attach(self, camera: BaseCamera, stage: BaseStage):
        """
        Retroactively attaches a camera and stage to the microscope object.

        Allows the microscope to be created as a "dummy", with hardware communications
        opened at a later time.

        Args:
            camera (:py:class:`openflexure_microscope.camera.base.BaseCamera`): camera object
            stage (:py:class:`openflexure_microscope.stage.base.BaseStage`): stage object
        """

        settings_full = self.read_config()

        logging.debug("Attaching camera...")
        self.camera = (
            camera
        )  #: :py:class:`openflexure_microscope.camera.base.BaseCamera`: Picamera object
        if not self.camera:
            logging.info("No camera attached.")
        else:
            logging.info("Attached camera {}".format(camera))

            if hasattr(self.camera, "lock"):  # If camera has a lock
                logging.info("Attaching {} to composite lock.".format(self.camera.lock))
                # Add the lock to the microscope composite lock
                self.lock.locks.append(self.camera.lock)

        logging.debug("Attaching stage...")
        self.stage = (
            stage
        )  #: :py:class:`openflexure_microscope.stage.base.BaseStage`: OpenFlexure stage object
        if not self.stage:
            logging.info("No stage attached.")
        else:
            logging.info("Attached stage {}".format(stage))

            if hasattr(self.stage, "lock"):  # If stage object has a lock
                logging.info(
                    "Attaching lock {} to composite lock.".format(self.stage.lock)
                )
                # Add the lock to the microscope composite lock
                self.lock.locks.append(self.stage.lock)

        logging.info("Reapplying settings to newly attached devices")
        self.apply_config(settings_full)

    def attach_plugins(self, plugin_maps: list):
        """
        Automatically search for plugin maps in config, and attach.
        """
        if plugin_maps:
            for plugin_map in plugin_maps:
                self.plugin.attach(plugin_map)
        else:
            logging.warning("No plugins specified. Skipping.")

    def reload_plugins(self):
        """
        Empty the plugin mount and re-attach from config.
        """
        logging.info("Tearing down existing PluginMount...")
        self.plugin = PluginMount(self)
        logging.info("Repopulating PluginMount...")
        self.attach_plugins(self.plugin_maps)

    # Create unified state
    @property
    def state(self):
        """Dictionary of the basic microscope state.

        Return:
            dict: Dictionary containing position data, 
                and :py:attr:`openflexure_microscope.camera.base.BaseCamera.state`
        """
        state = {
            "camera": self.camera.state,
            "stage": self.stage.state,
            "plugin": self.plugin.state,
            "version": pkg_resources.get_distribution("openflexure_microscope").version,
        }
        return state

    def apply_config(self, config: dict):
        """
        Applies a config dictionary. Missing parameters will be left untouched.
        """
        logging.debug("Microscope: Applying config: {}".format(config))

        # If attached to a camera
        if ("camera_settings" in config) and self.camera:
            self.camera.apply_config(config["camera_settings"])

        # If attached to a stage
        if ("stage_settings" in config) and self.stage:
            self.stage.apply_config(config["stage_settings"])

        # Todo: tidy up with some loopy goodness
        if "id" in config:
            self.id = config["id"]
        if "name" in config:
            self.name = config["name"]
        if "fov" in config:
            self.fov = config["fov"]
        if "plugins" in config:
            self.plugin_maps = config["plugins"]

    def read_config(self, json_safe=False):
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
            "fov": self.fov,
            "plugins": self.plugin_maps,
        }

        # If attached to a camera
        if self.camera:
            settings_current_camera = self.camera.read_config()
            settings_current["camera_settings"] = settings_current_camera

        # If attached to a stage
        if self.stage:
            settings_current_stage = self.stage.read_config()
            settings_current["stage_settings"] = settings_current_stage

        settings_full = self.settings_file.merge(settings_current)

        if json_safe:
            settings_full = settings_to_json(settings_full)

        return settings_full

    def save_config(self, backup: bool = True):
        """
        Merges the current settings back to disk
        """
        # Read curent config
        current_config = self.read_config()
        # Merge in server version responsible for saving the config file
        current_config["server_version"] = pkg_resources.get_distribution(
            "openflexure_microscope"
        ).version
        # Save config to file
        self.settings_file.save(current_config, backup=True)

    @property
    def config(self) -> dict:
        logging.warn(
            "Reading microscope through config property is deprecated.\
            Please use read_config method instead."
        )
        return self.read_config()

    @config.setter
    def config(self, config: dict) -> None:
        logging.warn(
            "Setting microscope through config property is deprecated.\
            Please use apply_config method instead."
        )
        self.apply_config(config)
