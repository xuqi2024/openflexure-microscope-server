import yaml
import os
import errno
import logging
import shutil
import copy
from fractions import Fraction
from collections import abc

"""
Attributes:
    USER_CONFIG_DIR (str): Default path of the user-config directory, containing runtime-config and
        calibration files. Obtained from ``os.path.join(os.path.expanduser("~"), ".openflexure")``.
    USER_CONFIG_FILE (str): Default path of the user microscope_settings.yaml runtime-config file. 
        Obtained from ``os.path.join(USER_CONFIG_DIR, "microscope_settings.yaml")``
"""

# HANDLE THE DEFAULT CONFIGURATION FILE

HERE = os.path.abspath(os.path.dirname(__file__))
DEFAULT_CONFIG_PATH = os.path.join(HERE, 'microscope_settings.default.yaml')

USER_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".openflexure")
USER_CONFIG_FILE = os.path.join(USER_CONFIG_DIR, "microscope_settings.yaml")

USER_CONFIG_FILE_OLD = os.path.join(USER_CONFIG_DIR, "microscoperc.yaml")

# Load the default config
with open(DEFAULT_CONFIG_PATH, 'r') as default_rc:
    DEFAULT_CONFIG = default_rc.read()

# Run a one-time conversion of the old microscoperc.yaml into the new microscope_settings.yaml
# TODO: Should be removed in >1.0.1?
if (not os.path.isfile(USER_CONFIG_FILE)) and (os.path.isfile(USER_CONFIG_FILE_OLD)):
    os.rename(USER_CONFIG_FILE_OLD, USER_CONFIG_FILE)


# HANDLE CUSTOM YAML PARSING
def construct_yaml_bool(self, node):
    """
    Override PyYAML constructors handling of bools.
    YAML otherwise caused grief for picamera properties where 'off' is a valid string value.
    """
    override_bool_values = {
            'yes':      True,
            'no':       False,
            'true':     True,
            'false':    False,
            'on':       'on',
            'off':      'off',
    }
    value = self.construct_scalar(node)
    return override_bool_values[value.lower()]


yaml.Loader.add_constructor(u'tag:yaml.org,2002:bool', construct_yaml_bool)


# HANDLE CONVERTING ARBITRARY CONFIG TO JSON-SAFE JSON

def convert_type_to_json_safe(v):
    """Make an individual attribute JSON-safe"""
    if isinstance(v, Fraction):
        return float(v)
    else:
        return v


def recursively_apply(data, func):
    """
    Recursively apply a function to a dictionary, list, array, or tuple

    Args:
        data: Input iterable data
        func: Function to apply to all non-iterable values
    """
    # If the object is a dictionary
    if isinstance(data, abc.Mapping):
        return {key: recursively_apply(val, func) for key, val in data.items()}
    # If the object is iterable but NOT a dictionary or a string
    elif (isinstance(data, abc.Iterable) and
          not isinstance(data, abc.Mapping) and
          not isinstance(data, str)):
        return [recursively_apply(x, func) for x in data]
    # if the object is neither a map nor iterable
    else:
        return func(data)


def settings_to_json(data: dict, clean_keys=True):
    """
    Make a copy of an input dictionary that's safe for JSON return

    Args:
        data: Input dictionary
        clean_keys: Modify any keys unsuitable for JSON return
    """

    # Do not overwrite original data dictionary
    d = copy.deepcopy(data)

    # If we're cleaning up unsuitable keys
    if clean_keys:
        # Convert lens_shading_table to a bool
        if 'picamera_settings' in d['camera_settings'] and 'lens_shading_table' in d['camera_settings']['picamera_settings']:
            logging.debug("Bool-ifying lens_shading_table")
            if d['camera_settings']['picamera_settings']['lens_shading_table'] is not None:
                d['camera_settings']['picamera_settings']['lens_shading_table'] = True

    return recursively_apply(d, convert_type_to_json_safe)


# HANDLE BASIC LOADING AND SAVING OF YAML FILES

def load_yaml_file(config_path) -> dict:
    """
    Open a .yaml config file

    Args:
        config_path (str): Path to the config YAML file. If `None`, defaults to `DEFAULT_CONFIG_PATH`
    """
    config_path = os.path.expanduser(config_path)

    logging.info("Loading {}...".format(config_path))

    with open(config_path) as config_file:
        config_data = yaml.load(config_file)

    # Return loaded config dictionary
    return config_data


def save_yaml_file(config_path: str, config_dict: dict, safe: bool = False):
    """
    Save a .yaml config file

    Args:
        config_dict (dict): Dictionary of config data to save.
        config_path (str): Path to the config YAML file.
        safe (bool): Whether to use PyYAML safe_dump instead of dump
    """
    config_path = os.path.expanduser(config_path)

    logging.info("Saving {}...".format(config_path))
    logging.debug(config_dict)

    with open(config_path, 'w') as outfile:
        if not safe:
            yaml.dump(config_dict, outfile)
        else:
            yaml.safe_dump(config_dict, outfile)


def create_file(config_path):
    if not os.path.exists(os.path.dirname(config_path)):
        try:
            os.makedirs(os.path.dirname(config_path))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise


def initialise_file(config_path, populate: str = ""):
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
        with open(config_path, 'w') as outfile:
            outfile.write(populate)


# MAIN CONFIG CLASS
class OpenflexureSettingsFile:
    """
    An object to handle expansion, conversion, and saving of the microscope configuration.

    Args:
        config_path (str): Path to the config YAML file (None falls back to default location)
        expand (bool): Expand paths to valid auxillary config files.
    """
    def __init__(self, config_path: str = None, expand: bool = True):
        global DEFAULT_CONFIG, USER_CONFIG_FILE

        self.expandable_keys = {
            'camera_settings': None,
            'stage_settings': None
        }  #: Dictionary of keys that can be passed as a file path string and expanded automatically

        # Set arguments
        self.config_path = config_path or USER_CONFIG_FILE
        self.expand = expand

        # Initialise basic config file with defaults if it doesn't exist
        initialise_file(self.config_path, populate=DEFAULT_CONFIG)

    def load(self):
        """
        Loads config from a file on-disk, and expands auxillary config files if available.
        """
        # Unexpanded config dictionary (used at load/save time)
        loaded_config = load_yaml_file(self.config_path)

        # If the loaded config is in contracted format
        if self.expand:
            # Expand self.raw_config into self._config
            loaded_config = self.expand_config(loaded_config)

        logging.debug("Reading settings from disk")
        return loaded_config

    def save(self, config: dict, backup: bool = True):
        """
        Save config to a file on-disk, and splits into auxillary config files if available.
        """
        # If the loaded config was in contracted format
        if self.expand:
            # Contract self._config into self.raw_config
            save_config = self.contract_config(config)
        else:
            save_config = config
    
        if backup:
            if os.path.isfile(self.config_path):
                shutil.copyfile(self.config_path, self.config_path+".bk")

        logging.debug("Saving settings dictionary to disk")
        save_yaml_file(self.config_path, save_config)

    def merge(self, config: dict, backup: bool = True):
        logging.debug("Merging settings with file on disk")
        settings = self.load()
        settings.update(config)

        return settings

    def expand_config(self, config_dict):
        """
        Search a config dictionary for paths to valid auxillary config files,
        and expand into the config dictionary if available.

        Args:
            config_dict (dict): Dictionary of config data to expand
        """
        return_config = {}
        if not config_dict:
            config_dict = {}
        # For each value in the raw loaded config
        for key, value in config_dict.items():
            # If it's a valid expandable parameter
            if (key in self.expandable_keys and
                    type(value) is str):

                logging.debug("Expanding {}".format(value))

                # Store expansion path
                self.expandable_keys[key] = config_dict[key]
                # Create the expansion file if it doesn't yet exist
                initialise_file(value)
                # Load the expansion file into _config
                return_config[key] = load_yaml_file(value) or {}
            else:
                return_config[key] = value

        return return_config

    def contract_config(self, config_dict):
        """
        Split a config dictionary into auxillary config files, if available.

        Args:
            config_dict (dict): Dictionary of config data to contract/split
        """
        return_config = {}
        # For each value in the expanded config
        for key, value in config_dict.items():
            # If it's a valid expandable parameter
            if (key in self.expandable_keys and
                    self.expandable_keys[key] is not None and
                    type(value) is dict):

                logging.debug("Saving to {}".format(self.expandable_keys[key]))
                # Create the file if it doesn't exist
                initialise_file(self.expandable_keys[key])
                # Save the expanded config dictionary to the file
                save_yaml_file(self.expandable_keys[key], value)
                # Replace the expanded dictionary with a file path
                return_config[key] = self.expandable_keys[key]
            else:
                return_config[key] = value

        return return_config
