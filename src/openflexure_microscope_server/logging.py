import logging
from logging.handlers import RotatingFileHandler
import os
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse

OFM_LOG_FOLDER = "/var/openflexure/logs/"
OFM_LOG_FILE = os.path.join(OFM_LOG_FOLDER, "openflexure_microscope.log")


def configure_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    try:
        if not os.path.exists(OFM_LOG_FOLDER):
            os.makedirs(OFM_LOG_FOLDER)
        handler = RotatingFileHandler(
            filename=OFM_LOG_FILE,
            mode="a",
            maxBytes=1000000,
            backupCount=10,
        )
        format_str = "[%(asctime)s] [%(levelname)s] <%(name)s> %(message)s"
        handler.setFormatter(logging.Formatter(format_str))
        root_logger.addHandler(handler)
        root_logger.addHandler(OFM_HANDLER)

    except PermissionError as e:
        logging.warning(f"Cannot create log file at {OFM_LOG_FILE}: {e}")
    logging.info("")
    logging.info("****************************************************")
    logging.info("OFM server root logger has been set up at INFO level")
    logging.info("****************************************************")


def retrieve_log() -> PlainTextResponse:
    """
    Returns logs since we started running the server, up to a maxiumum of
    250 messages. This log is the one shown in the UI and on the logging page.

    It does not include any of the `uvicorn.access` logs as these are emmitted
    every time any API route is called.

    All logs, including `uvicorn.access` are logged to the OFM_LOG_FILE (see above)
    ths is the best place to get logs about crashes.
    """
    return JSONResponse(content=jsonable_encoder(OFM_HANDLER.log_history))


def retrieve_log_from_file() -> PlainTextResponse:
    """
    Returns the full log from the file for downloading.

    Note this is read and then sent as otherwise it causes a RuntimeError if it
    is written to while sending through FileResponse
    """
    with open(OFM_LOG_FILE, "r", encoding="utf-8") as logfile:
        full_log = logfile.read()
    return PlainTextResponse(full_log)


class OFMHandler(logging.Handler):
    """
    A child class of logging.Handler. This class handles storing the most recent
    logs for access by the server.
    """

    def __init__(self, level=logging.INFO, max_logs=250):
        super().__init__(level=level)
        self._log = []
        self._max_logs = max_logs
        # start at -1 so first record is 0
        self._running_counter = -1

    def _as_record_dict(self, record):
        """
        Format the record into the dictoionary structure expected by the server
        """
        msg = record.message
        self._running_counter += 1
        return {
            "timestamp": record.asctime,
            "level": record.levelname,
            "summary": msg.split("\n")[0],
            "message": record.getMessage(),
            "sequence": self._running_counter,
            "expanded": False,
        }

    def append_record(self, record):
        """
        Use the built in formatter to format the record, then save
        it to an array. Pop any in excess of the maximum number of logs
        """
        self._log.append(self._as_record_dict(record))
        while len(self._log) > self._max_logs:
            self._log.pop(0)

    def emit(self, record):
        """
        Emit will save the logged record to the log
        """

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
        """
        Return the log history up to the maximum number of logs
        """
        return list(reversed(self._log))


OFM_HANDLER = OFMHandler()
