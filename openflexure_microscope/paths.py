import os
import logging

# UTILITIES


def check_rw(path):
    return os.access(path, os.W_OK) and os.access(path, os.R_OK)


def settings_file_path(filename: str):
    """Generate a full file path for a filename to be stored in server settings folder"""
    settings_dir = os.path.join(OPENFLEXURE_VAR_PATH, "settings")
    if not os.path.exists(settings_dir):
        os.makedirs(settings_dir)
    return os.path.join(settings_dir, filename)


def data_file_path(filename: str):
    """Generate a full file path for a filename to be stored in server data folder"""
    data_dir = os.path.join(OPENFLEXURE_VAR_PATH, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)


def extensions_file_path(filename: str):
    """Generate a full file path for a folder to be stored in server extensions"""
    ext_dir = os.path.join(OPENFLEXURE_VAR_PATH, "extensions")
    if not os.path.exists(ext_dir):
        os.makedirs(ext_dir)
    return os.path.join(ext_dir, filename)


def logs_file_path(filename: str):
    """Generate a full file path for a filename to be stored in server logs"""
    logs_dir = os.path.join(OPENFLEXURE_VAR_PATH, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    return os.path.join(logs_dir, filename)


# HANDLE DEFAULTS FILES STORED IN THIS APPLICATION

HERE = os.path.abspath(os.path.dirname(__file__))

#: Path of default (first-run) microscope settings
DEFAULT_SETTINGS_FILE_PATH = os.path.join(HERE, "microscope_settings.default.json")
#: Path of default (first-run) microscope configuration
DEFAULT_CONFIGURATION_FILE_PATH = os.path.join(
    HERE, "microscope_configuration.default.json"
)

# BASE PATHS

if os.name == "nt":
    PREFERRED_VAR_PATH = os.getenv("PROGRAMDATA") or "C:\\ProgramData"
    FALLBACK_VAR_PATH = os.path.expanduser("~")
else:
    PREFERRED_VAR_PATH = "/var"
    FALLBACK_VAR_PATH = os.path.expanduser("~")

PREFERRED_OPENFLEXURE_VAR_PATH = os.path.join(PREFERRED_VAR_PATH, "openflexure")
FALLBACK_OPENFLEXURE_VAR_PATH = os.path.join(FALLBACK_VAR_PATH, "openflexure")

if not os.path.exists(PREFERRED_OPENFLEXURE_VAR_PATH) and check_rw(PREFERRED_VAR_PATH):
    os.makedirs(PREFERRED_OPENFLEXURE_VAR_PATH)

if check_rw(PREFERRED_OPENFLEXURE_VAR_PATH):
    OPENFLEXURE_VAR_PATH = PREFERRED_OPENFLEXURE_VAR_PATH
else:
    if not os.path.exists(FALLBACK_OPENFLEXURE_VAR_PATH):
        os.makedirs(FALLBACK_OPENFLEXURE_VAR_PATH)
    OPENFLEXURE_VAR_PATH = FALLBACK_OPENFLEXURE_VAR_PATH


# SERVER PATHS

#: Path of microscope settings file
SETTINGS_FILE_PATH = settings_file_path("microscope_settings.json")
#: Path of microscope configuration file
CONFIGURATION_FILE_PATH = settings_file_path("microscope_configuration.json")
#: Path of microscope extensions directory
OPENFLEXURE_EXTENSIONS_PATH = extensions_file_path("microscope_extensions")
