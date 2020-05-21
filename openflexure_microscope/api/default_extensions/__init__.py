import logging
import traceback
from contextlib import contextmanager


@contextmanager
def handle_extension_error(extension_name):
    """'gracefully' log an error if an extension fails to load."""
    try:
        yield
    except Exception as e:
        logging.error(
            f"Exception loading builtin extension picamera_autocalibrate: \n{traceback.format_exc()}"
        )


with handle_extension_error("autofocus"):
    from .autofocus import autofocus_extension_v2
with handle_extension_error("scan"):
    from .scan import scan_extension_v2
with handle_extension_error("zip builder"):
    from .zip_builder import zip_extension_v2
with handle_extension_error("autostorage"):
    from .autostorage import autostorage_extension_v2
with handle_extension_error("camera stage mapping"):
    from camera_stage_mapping.ofm_extension import csm_extension
with handle_extension_error("lens shading calibration"):
    from .picamera_autocalibrate import lst_extension_v2
