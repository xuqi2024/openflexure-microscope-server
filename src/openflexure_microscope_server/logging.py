import logging
from logging.handlers import RotatingFileHandler
import os

from fastapi.responses import FileResponse, PlainTextResponse

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
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        )
        root_logger.addHandler(handler)
    except PermissionError as e:
        logging.warning(f"Cannot create log file at {OFM_LOG_FILE}: {e}")
    logging.info("")
    logging.info("****************************************************")
    logging.info("OFM server root logger has been set up at INFO level")
    logging.info("****************************************************")


def retrieve_log() -> PlainTextResponse:
    """The most recent 1Mb of logs from the server"""
    return FileResponse(OFM_LOG_FILE, media_type=PlainTextResponse.media_type)
