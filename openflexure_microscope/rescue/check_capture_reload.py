from openflexure_microscope.rescue.monitor_timeout import launch_timeout_test_process
from openflexure_microscope.camera.capture import build_captures_from_exif
from openflexure_microscope.camera.base import BASE_CAPTURE_PATH
from openflexure_microscope.config import user_settings

import logging


def check_capture_rebuild(timeout=10):
    logging.info("Loading user settings...")
    settings = user_settings.load()

    cap_path = str(settings.get("camera", {}).get("paths", {}).get("default"))
    logging.info(f"Capture path found: {cap_path}")
    if not cap_path:
        logging.error(
            "No capture path defined in settings. This is unusual for anything other than a first-run. \nFalling back to default path."
        )
        cap_path = BASE_CAPTURE_PATH

    logging.info("Starting capture reload with a 10 second timeout...")
    passed_timeout_test = launch_timeout_test_process(
        build_captures_from_exif, args=(cap_path,)
    )

    return passed_timeout_test


def main():
    error_sources = []
    passed_timeout = check_capture_rebuild()
    if not passed_timeout:
        error_sources.append("capture_rebuild_timeout")
    return error_sources
