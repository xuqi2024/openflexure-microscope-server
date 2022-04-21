import os
from typing import List, Optional

# UTILITIES


def check_rw(path: str) -> bool:
    return os.access(path, os.W_OK) and os.access(path, os.R_OK)


def settings_file_path(filename: str) -> str:
    """Generate a full file path for a filename to be stored in server settings folder"""
    settings_dir = os.path.join(OPENFLEXURE_DIR, "settings")
    if not os.path.exists(settings_dir):
        os.makedirs(settings_dir)
    return os.path.join(settings_dir, filename)


def data_file_path(filename: str) -> str:
    """Generate a full file path for a filename to be stored in server data folder"""
    data_dir = os.path.join(OPENFLEXURE_DIR, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)


def extensions_file_path(filename: str) -> str:
    """Generate a full file path for a folder to be stored in server extensions"""
    ext_dir = os.path.join(OPENFLEXURE_DIR, "extensions")
    if not os.path.exists(ext_dir):
        os.makedirs(ext_dir)
    return os.path.join(ext_dir, filename)


def logs_file_path(filename: str) -> str:
    """Generate a full file path for a filename to be stored in server logs"""
    logs_dir = os.path.join(OPENFLEXURE_DIR, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    return os.path.join(logs_dir, filename)


def first_path_that_exists(search_path: List[str]) -> Optional[str]:
    """Return the first path in a list that exists"""
    for path in search_path:
        if os.path.exists(path):
            return path
    return None

def first_path_that_is_creatable(search_path: List[str]) -> Optional[str]:
    """Return the first path in a list that could be created
    
    "could be created" here means that the parent directory exists and
    is writeable.
    """
    for path in search_path:
        if check_rw(os.path.split(path)[0]):
            return path
    return None


if os.name == "nt":
    SYSTEM_VAR_PATH: str = os.getenv("PROGRAMDATA") or "C:\\ProgramData"
else:
    SYSTEM_VAR_PATH: str = "/var"

OPENFLEXURE_DIR_SEARCH_PATH = [
    os.path.join(SYSTEM_VAR_PATH, "openflexure"),
    os.path.join(os.path.expanduser("~"), "openflexure"),
]

CONFIG_FILE_SEARCH_PATH = [
    os.path.join(p, "microscope_configuration.json")
    for p in OPENFLEXURE_DIR_SEARCH_PATH
] + ["microscope_configuration.json"]


def default_openflexure_dir() -> str:
    """The default openflexure directory
    
    The openflexure directory contains the logs, settings, and other
    files the server needs to run.  We look in a few places for an 
    existing directory (a system-level one is tried first, either
    `/var` or `C:\\ProgramData` depending on your system.  Next, we
    check for an `openflexure` folder in the current user's home
    directory.
    
    If no existing directory is found, we then check to see which
    of those locations could be created (same search order), and 
    return that.

    If there isn't an openflexure directory, and we can't create 
    one, we raise an exception.

    Note that this function will never create a directory - that is
    done elsewhere.
    """
    dir = first_path_that_exists(OPENFLEXURE_DIR_SEARCH_PATH)
    if dir:
        return dir
    dir = first_path_that_is_creatable(OPENFLEXURE_DIR_SEARCH_PATH)
    if dir:
        return dir
    else:
        raise FileNotFoundError(
            "The OpenFlexure directory was not found at any of the "
            "search locations, and could not be created in any of "
            "those locations.  Please create it manually, fix "
            "permissions, and/or specify a directory in your "
            "configuration file."
        )


OPENFLEXURE_DIR = None  # Formerly OPENFLEXURE_VAR_PATH
SETTINGS_FILE_PATH = None


def initialise_paths(openflexure_dir: Optional[str] = None):
    """Check the openflexure directory exists and create if needed.
    
    This function should be called **after** loading configuration
    (in case the config file customises the openflexure directory's 
    location) but **before** any code attempts to use the paths
    defined in this file.
    
    This is a compromise between passing all the configuration
    paths explicitly (which would make the data flow clearer, but
    introduce a lot more verbosity into the code) and having all
    the paths defined at import time (which makes debugging and
    testing much harder, but saves passing paths around).
    """
    if not openflexure_dir:
        openflexure_dir = default_openflexure_dir()
    assert openflexure_dir is not None  # primarily for type-checking

    if not os.path.isdir(openflexure_dir):
        os.makedirs(openflexure_dir)

    global OPENFLEXURE_DIR
    OPENFLEXURE_DIR = openflexure_dir
