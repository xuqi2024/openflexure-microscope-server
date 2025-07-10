"""Configure logging for the OpenFlexure Server.

A module containing a custom logging handler and helper function for
the OpenFlexure server. These handle formatting logs, ensuring that logs
are logged both to a file and to the terminal (see note below!). Functionality
is also provided for retrieving logs for to send over HTTP.

Note that when running in production OpenFlexure Microscope the server is run via
``systemd``. As such, the logs that are sent to the terminal (STDERR) or any other
output to STDOUT/STDERR are captured by ``systemd``. These can be viewed by using
``journalctl`` or the ``ofm journal`` command.
"""

import logging
from logging.handlers import RotatingFileHandler
import os

from fastapi.responses import PlainTextResponse

OFM_LOG_FILE = None


def configure_logging(log_folder):
    """Configure logging for the server while it is running.

    This modifies the root logger to have a rotating file handler and
    adds a custom handler that prints and stores all records except
    ``uvicorn.access`` logs.

    It is important not to let Uvicorn override these settings.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Explictly make OFM_LOG_FILE a global so it can be updated based on log settings
    global OFM_LOG_FILE
    OFM_LOG_FILE = os.path.join(log_folder, "openflexure_microscope.log")

    try:
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        handler = RotatingFileHandler(
            filename=OFM_LOG_FILE,
            mode="a",
            maxBytes=1000000,
            backupCount=10,
        )
        format_str = "[%(asctime)s] [%(levelname)s] <%(name)s> %(message)s"
        handler.setFormatter(logging.Formatter(format_str))
        root_logger.addHandler(handler)
        ofm_format_str = "[%(asctime)s] [%(levelname)s] %(message)s"
        OFM_HANDLER.setFormatter(logging.Formatter(ofm_format_str))
        root_logger.addHandler(OFM_HANDLER)

    except PermissionError as e:
        logging.warning(f"Cannot create log file at {OFM_LOG_FILE}: {e}")
    logging.info("")
    logging.info("****************************************************")
    logging.info("OFM server root logger has been set up at INFO level")
    logging.info("****************************************************")


def retrieve_log() -> PlainTextResponse:
    """Return logs since the server started, up to a maximum of 250 messages.

    This log is the one shown in the UI and on the logging page.

    It does not include any of the ``uvicorn.access`` logs as these are emmitted
    every time any API route is called.

    All logs, including ``uvicorn.access`` are logged to the OFM_LOG_FILE (see above)
    ths is the best place to get logs about crashes.
    """
    return PlainTextResponse(OFM_HANDLER.log_history)


def retrieve_log_from_file() -> PlainTextResponse:
    """Return the full log from the file for downloading.

    Note this is read and then sent as otherwise it causes a RuntimeError if it
    is written to while sending through FileResponse.
    """
    if OFM_LOG_FILE is None:
        raise RuntimeError(
            "Cannot retrieve log file as logging directory hasn't been configured"
        )
    with open(OFM_LOG_FILE, "r", encoding="utf-8") as logfile:
        full_log = logfile.read()
    return PlainTextResponse(full_log)


class OFMHandler(logging.Handler):
    """A logging.Handler that stores the most recent logs for access by the server."""

    def __init__(self, level=logging.INFO, max_logs=250):
        super().__init__(level=level)
        self._log = []
        self._max_logs = max_logs

    def append_record(self, record):
        """Format message and append it to a list of records.

        The built in formatter is used to format the record.

        Any records in excess of the maximum number of logs are removed.
        """
        self._log.append(self.format(record))
        while len(self._log) > self._max_logs:
            self._log.pop(0)

    def emit(self, record):
        """Emit will save the logged record to the log."""
        # Basic filter for now that simply stops uvicorn.access logs
        # These are the logs each time an API endpoint is accessed
        # This is only the log for the UI.
        if record.name.startswith("uvicorn.access"):
            return
        try:
            if record.levelno >= self.level:
                self.append_record(record)
        except RecursionError as e:
            raise e
        except BaseException:
            # Never let the logger crash unless there is somehow recursion.
            # Use built in logging error handler
            self.handleError(record)

    @property
    def log_history(self):
        """Return the log history up to the maximum number of logs."""
        return "\n".join(self._log)


OFM_HANDLER = OFMHandler()
