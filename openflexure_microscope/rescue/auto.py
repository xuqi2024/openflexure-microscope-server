from openflexure_microscope.paths import (
    FALLBACK_OPENFLEXURE_VAR_PATH,
    PREFERRED_OPENFLEXURE_VAR_PATH,
)
import logging
import os

from . import check_settings, check_capture_reload

# Paths for suggestions
LOGS_PATHS = [
    os.path.join(PREFERRED_OPENFLEXURE_VAR_PATH, "logs"),
    os.path.join(FALLBACK_OPENFLEXURE_VAR_PATH, "logs"),
]
SETTINGS_PATHS = [
    os.path.join(var_path, "settings", "microscope_settings.json")
    for var_path in (PREFERRED_OPENFLEXURE_VAR_PATH, FALLBACK_OPENFLEXURE_VAR_PATH)
]
CONFIG_PATHS = [
    os.path.join(var_path, "settings", "microscope_configuration.json")
    for var_path in (PREFERRED_OPENFLEXURE_VAR_PATH, FALLBACK_OPENFLEXURE_VAR_PATH)
]
DATA_PATHS = [
    os.path.join(PREFERRED_OPENFLEXURE_VAR_PATH, "data"),
    os.path.join(FALLBACK_OPENFLEXURE_VAR_PATH, "data"),
]

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.debug("Testing debug logger. One two one two.")


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


error_keys = {
    "config_settings_import_error": "The configuration submodule could not be imported properly. This is usually because the default config or settings files are badly broken somehow. See further errors for details",
    "default_config_empty": "The default configuration file is empty, and could not be automatically populated.",
    "default_settings_empty": "The default settings file is empty, and could not be automatically populated.",
    "default_config_error": f"The default configuration file could not be parsed. To fix, consider backing up and deleting your configuration files from {CONFIG_PATHS} to reset the configuration.",
    "default_settings_error": f"The default settings file could not be parsed. To fix, consider backing up and deleting your configuration files from {SETTINGS_PATHS} to reset the configuration.",
    "capture_rebuild_timeout": f"Capture database rebuilding took a long time. This may not cause catastrophic errors, but rather will cause the server to hang for a while. To fix, consider moving your captures from {DATA_PATHS} to another location.",
}

if __name__ == "__main__":
    spoof = False

    error_sources = []

    if spoof:
        error_sources = list(error_keys.keys())

    error_sources.extend(check_settings.main())
    error_sources.extend(check_capture_reload.main())

    if not error_sources:

        print()
        print(bcolors.OKGREEN + "No errors found!" + bcolors.ENDC)
        print(
            "That's not to say everything is fine, only that our automatic diagnostics couldn't find much."
        )
        print(f"You can check through the server logs at {LOGS_PATHS}")

    else:
        for err_code in error_sources:
            logging.error(err_code)
            if error_keys.get(err_code):
                print(bcolors.FAIL + error_keys.get(err_code) + bcolors.ENDC)
