import logging
import json

ERROR_SOURCES = []


def trace_config_exceptions():
    error_sources = []

    from openflexure_microscope.paths import (
        DEFAULT_CONFIGURATION_FILE_PATH,
        SETTINGS_FILE_PATH,
    )

    try:
        default_config = json.load(DEFAULT_CONFIGURATION_FILE_PATH)
        if not default_config:
            error_sources.append("default_config_empty")
    except Exception as e:
        logging.error("Error parsing config:")
        logging.error(e)
        error_sources.append("default_config_error")

    try:
        default_settings = json.load(SETTINGS_FILE_PATH)
        if not default_settings:
            error_sources.append("default_settings_empty")
    except Exception as e:
        logging.error("Error parsing settings:")
        logging.error(e)
        error_sources.append("default_settings_error")

    return error_sources


def main():
    error_sources = []
    logging.info("Attempting default settings and config import...")
    try:
        from openflexure_microscope import config
    except Exception as e:
        error_sources.append("config_settings_import_error")
        logging.error("Error importing config:")
        logging.error(e)
        error_sources.extend(trace_config_exceptions())

    return error_sources
