"""
Set up logging for the OFM Server

This file sets up logging for the application, splitting access and application logs.
This is done as an import-time side effect, so that it's done once while everything is
set up.
"""

import datetime
import logging
import logging.handlers
import os
import sys

from flask import send_file, abort
from labthings.views import View
from typing import Optional


ROOT_LOGFILE: Optional[str] = None
ACCESS_LOGFILE: Optional[str] = None


# Custom RotatingFileHandler subclass
class CustomRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    A custom class for a rotating file log handler, with defaults we like.
    1MB per file, maximum of 5 historic files.
    Non-propagating logs (so we can separate access logs from error logs)
    Optional debugging level.
    """

    def __init__(self, filename: str, debug: bool = False) -> None:
        super().__init__(filename, maxBytes=1_000_000, backupCount=5)
        # Set formatter
        self.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(threadName)s] [%(levelname)s] %(message)s"
            )
        )
        # Never propagate
        self.propagate: bool = False
        # Conditionally enable debugging
        if debug:
            self.setLevel(logging.DEBUG)


def configure_logging(log_folder: str):
    # Look for debug flag
    if "-d" in sys.argv or "--debug" in sys.argv:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    # Set root logger level
    root_log: logging.Logger = logging.getLogger()
    root_log.setLevel(log_level)

    # Log files
    global ROOT_LOGFILE, ACCESS_LOGFILE
    ROOT_LOGFILE = os.path.join(log_folder, "openflexure_microscope.log")
    ACCESS_LOGFILE = os.path.join(log_folder, "openflexure_microscope.access.log")

    # Our WSGI server uses Werkzeug, so use that for the access log
    access_log: logging.Logger = logging.getLogger("werkzeug")
    # Block the access logs from propagating up to the root logger
    access_log.propagate = False

    # Create error log file handler
    fh: logging.Handler = CustomRotatingFileHandler(
        ROOT_LOGFILE, debug=log_level == logging.DEBUG
    )
    # Create access log file handler
    afh: logging.Handler = CustomRotatingFileHandler(
        ACCESS_LOGFILE, debug=log_level == logging.DEBUG
    )
    # Add file handler to root logger
    root_log.addHandler(fh)
    access_log.addHandler(afh)


def root_log_level():
    """The current level of the root logger"""
    root_log: logging.Logger = logging.getLogger()
    return root_log.getEffectiveLevel()


def root_debug():
    """Returns True if the root logger is set to DEBUG"""
    return root_log_level() == logging.DEBUG


# Add log file download view
class LogFileView(View):
    def get(self):
        """
        Most recent 1mb of log output
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if not ROOT_LOGFILE:
            abort(500, "The log file has not been configured yet.")
        return send_file(
            ROOT_LOGFILE,
            as_attachment=True,
            attachment_filename="openflexure_microscope_{}.log".format(timestamp),
        )
