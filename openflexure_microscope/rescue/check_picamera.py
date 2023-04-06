import logging

from .error_sources import ErrorSource

# Error/exception messages we have enumerated and expect
PICAMERA_ERROR_MAP = {
    "Camera is not enabled. Try running 'sudo raspi-config' and ensure that the camera has been enabled.": ErrorSource(
        "Camera is not enabled. Try running 'sudo raspi-config' and ensure that the camera has been enabled."
    ),
    "Failed to enable connection: Out of resources": ErrorSource(
        "Camera already in use by another application. Please reboot your microscope."
    ),
}

# Basic import error. Usually damaged or disconnected camera
PICAMERA_IMPORT_ERROR = ErrorSource(
    (
        "Picamera module could not be imported. Check physical connections to the camera as it may be damaged or disconnected.",
    )
)


def main():
    error_sources = []
    logging.info("Attempting to import picamera...")

    try:
        import picamerax
    except Exception as _e:  # pylint: disable=W0703
        error_sources.append(PICAMERA_IMPORT_ERROR)
    else:
        try:
            _cam = picamerax.PiCamera()
        except picamerax.PiCameraError as e:
            msg = e.args[0]
            if msg in PICAMERA_ERROR_MAP:
                error_sources.append(PICAMERA_ERROR_MAP[msg])
            else:
                error_sources.append(ErrorSource("Unenumerated exception: " + msg))

    return error_sources
