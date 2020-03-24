import json
import flask
import os
import errno
import logging
import shutil
from uuid import UUID
import numpy as np
from fractions import Fraction

from .paths import (
    SETTINGS_FILE_PATH,
    DEFAULT_SETTINGS_FILE_PATH,
    CONFIGURATION_FILE_PATH,
    DEFAULT_CONFIGURATION_FILE_PATH,
)


class OpenflexureSettingsFile:
    """
    An object to handle expansion, conversion, and saving of the microscope configuration.

    Args:
        config_path (str): Path to the config JSON file (None falls back to default location)
        expand (bool): Expand paths to valid auxillary config files.
    """

    def __init__(self, path: str, defaults: dict = {}):
        global DEFAULT_SETTINGS

        # Set arguments
        self.path = path

        # Initialise basic config file with defaults if it doesn't exist
        initialise_file(self.path, populate=defaults)

    def load(self) -> dict:
        """
        Loads settings from a file on-disk.
        """
        # Unexpanded config dictionary (used at load/save time)
        loaded_config = load_json_file(self.path)

        logging.debug("Reading settings from disk")
        return loaded_config

    def save(self, config: dict, backup: bool = True):
        """
        Save settings to a file on-disk.

        Args:
            config (dict): Dictionary of new settings
            backup (bool): Back up previous settings file
        """

        save_settings = config

        if backup:
            if os.path.isfile(self.path):
                shutil.copyfile(self.path, self.path + ".bk")

        logging.debug("Saving settings dictionary to disk")
        save_json_file(self.path, save_settings)

    def merge(self, config: dict) -> dict:
        """
        Merge settings dictionary with settings loaded from file on-disk.

        Args:
            config (dict): Dictionary of new settings
        """

        logging.debug("Merging settings with file on disk")
        settings = self.load()
        settings.update(config)

        return settings


class JSONEncoder(flask.json.JSONEncoder):
    """
    A custom JSON encoder, with type conversions for PiCamera fractions, Numpy integers, and Numpy arrays
    """

    def default(self, o, markers=None):
        if isinstance(o, UUID):
            return str(o)
        # PiCamera fractions
        elif isinstance(o, Fraction):
            return float(o)
        # Numpy integers
        elif isinstance(o, np.integer):
            return int(o)
        # Numpy arrays
        elif isinstance(o, np.ndarray):
            return o.tolist()
        # UUIDs
        elif isinstance(o, UUID):
            return str(o)
        else:
            # call base class implementation which takes care of
            # raising exceptions for unsupported types
            return flask.json.JSONEncoder.default(self, o)


# HANDLE BASIC LOADING AND SAVING OF SETTINGS FILES


def load_json_file(config_path) -> dict:
    """
    Open a .json config file

    Args:
        config_path (str): Path to the config JSON file. If `None`, defaults to `DEFAULT_CONFIG_PATH`
    """
    config_path = os.path.expanduser(config_path)

    logging.info("Loading {}...".format(config_path))

    with open(config_path) as config_file:
        try:
            config_data = json.load(config_file)
        except json.decoder.JSONDecodeError as e:
            logging.error(e)
            config_data = {}

    # Return loaded config dictionary
    return config_data


def save_json_file(config_path: str, config_dict: dict):
    """
    Save a .json config file

    Args:
        config_dict (dict): Dictionary of config data to save.
        config_path (str): Path to the config JSON file.
    """
    config_path = os.path.expanduser(config_path)

    logging.info("Saving {}...".format(config_path))
    logging.debug(config_dict)

    with open(config_path, "w") as outfile:
        json.dump(config_dict, outfile, cls=JSONEncoder, indent=2, sort_keys=True)


def create_file(config_path):
    """
    Creates an empty file, and all folder structure currently nonexistant.

    Args:
        config_path: Path to the (possibly) new file
    """
    if not os.path.exists(os.path.dirname(config_path)):
        try:
            os.makedirs(os.path.dirname(config_path))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise


def initialise_file(config_path, populate: str = "{}\n"):
    """
    Check if a file exists, and if not, create it
    and optionally populate it with content

    Args:
        config_path (str): Path to the file.
        populate (str): String to dump to the file, if it is being newly created
    """
    config_path = os.path.expanduser(config_path)

    logging.debug("Initialising {}".format(config_path))
    logging.debug("Exists: {}".format(os.path.exists(config_path)))

    if not os.path.exists(config_path):  # If user config file doesn't exist
        logging.warning("No config file found at {}. Creating...".format(config_path))
        create_file(config_path)

        logging.info("Populating {}...".format(config_path))
        with open(config_path, "w") as outfile:
            outfile.write(populate)


# Load the default settings
with open(DEFAULT_SETTINGS_FILE_PATH, "r") as default_settings:
    DEFAULT_SETTINGS = default_settings.read()

#: Default user settings object
user_settings = OpenflexureSettingsFile(
    path=SETTINGS_FILE_PATH, defaults=DEFAULT_SETTINGS
)


# Load the default configuration
with open(DEFAULT_CONFIGURATION_FILE_PATH, "r") as default_configuration:
    DEFAULT_CONFIGURATION = default_configuration.read()

#: Default user settings object
user_configuration = OpenflexureSettingsFile(
    path=CONFIGURATION_FILE_PATH, defaults=DEFAULT_CONFIGURATION
)

