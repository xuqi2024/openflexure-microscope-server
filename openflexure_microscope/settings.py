import errno
import json
import logging
import os
import shutil

from .json import JSONEncoder


class OpenflexureSettingsFile:
    """
    An object to handle expansion, conversion, and saving of the microscope configuration.

    Args:
        config_path (str): Path to the config JSON file (None falls back to default location)
        expand (bool): Expand paths to valid auxillary config files.
    """

    def __init__(self, path: str, defaults: dict = None):
        defaults = defaults or {}

        # Set arguments
        self.path = path

        # Initialise basic config file with defaults if it doesn't exist
        initialise_file(
            self.path,
            # Populate with default dictionary, or empty JSON if empty
            populate=json.dumps(defaults, cls=JSONEncoder, indent=2, sort_keys=True)
            or "{}\n",
        )

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


# HANDLE BASIC LOADING AND SAVING OF SETTINGS FILES


def load_json_file(config_path) -> dict:
    """
    Open a .json config file

    Args:
        config_path (str): Path to the config JSON file. If `None`, defaults to `DEFAULT_CONFIG_PATH`
    """
    config_path = os.path.expanduser(config_path)

    logging.info("Loading %s...", config_path)

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

    logging.info("Saving %s...", config_path)
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

    logging.debug("Initialising %s", (config_path))
    logging.debug("Exists: %s", (os.path.exists(config_path)))

    if not os.path.exists(config_path):  # If user config file doesn't exist
        logging.warning("No config file found at %s. Creating...", (config_path))
        create_file(config_path)

        logging.info("Populating %s...", (config_path))
        with open(config_path, "w") as outfile:
            outfile.write(populate)

#: Default user settings object 
# TODO: lazy-load this or otherwise make it obey the path initialisation...
raise NotImplementedError("Need to find a better way to manage settings!")
user_settings = OpenflexureSettingsFile(path="")