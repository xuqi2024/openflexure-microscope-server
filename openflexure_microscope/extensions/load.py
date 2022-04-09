"""Load the extensions from the configuration file"""

import logging
import os

from labthings.extensions import find_extensions
from openflexure_microscope.paths import OPENFLEXURE_EXTENSIONS_PATH
from . import find

def load_extensions(config):
    """Load extensions defined in config file and folder
    
    For now, this attempts to load all the extensions defined in the
    configuration file, and return a list of extension instances.
    We also attempt to load all extensions from the folder, if the
    corresponding option is set in the config file.
    """
    extensions = []
    # New-style extensions are explicitly enabled in the configuration file
    extension_entry_points = find.entry_points_from_list(
        config.get("extensions_enabled", [])
    )
    for entrypoint in extension_entry_points:
        extension_class = entrypoint.load()
        extensions.append(extension_class())
    if config.get("enable_legacy_extensions_folder", True):
        # This loads old-style extensions and is deprecated
        if os.path.isfile(OPENFLEXURE_EXTENSIONS_PATH):
            for extension in find_extensions(OPENFLEXURE_EXTENSIONS_PATH):
                logging.warning(
                    f"Using an old-style extension {extension.__name__}.  "
                    "Support for this will be removed in the future."
                )
                extensions.append(extension)
    return extensions