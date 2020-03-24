import logging
import traceback

from .autofocus import autofocus_extension_v2
from .scan import scan_extension_v2
from .zip_builder import zip_extension_v2
from .autostorage import autostorage_extension_v2

# "Gracefully" handle cases where picamera cannot be imported (eg test server)
try:
    from .picamera_autocalibrate import lst_extension_v2
except Exception as e:
    logging.error(
        f"Exception loading builtin extension picamera_autocalibrate: \n{traceback.format_exc()}"
    )
