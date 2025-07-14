"""Test the server's logging configuration and handling."""

import os
import tempfile
import logging

from fastapi.responses import PlainTextResponse
from fastapi import HTTPException
import pytest

from openflexure_microscope_server import logging as ofm_logging


def test_no_warnings_if_correct_permissions(caplog):
    """Check that configure_logging no warnings on normal operation.

    Checking that:

    * The logger can be set up without warnings.
    * That the log file is created.
    * That the log file contains the expected message about setting up the logger.
    """
    # Reset handler at start of test
    ofm_logging.OFM_HANDLER = ofm_logging.OFMHandler()
    with caplog.at_level(logging.WARNING):
        with tempfile.TemporaryDirectory() as tmpdir:
            ofm_logging.configure_logging(tmpdir)
            assert len(caplog.records) == 0
            with open(ofm_logging.OFM_LOG_FILE, "r", encoding="utf-8") as log_file:
                log_txt = log_file.read()
            assert "OFM server root logger has been set up at INFO level" in log_txt
            root_logger = logging.getLogger()
            assert ofm_logging.OFM_HANDLER in root_logger.handlers


def test_permission_error_raises_warning(mocker, caplog):
    """Check that configure_logging raises warning on PermissionError."""
    mocker.patch(
        "openflexure_microscope_server.logging.RotatingFileHandler",
        side_effect=PermissionError("Permission denied"),
    )
    # Reset handler at start of test
    ofm_logging.OFM_HANDLER = ofm_logging.OFMHandler()
    with caplog.at_level(logging.WARNING):
        with tempfile.TemporaryDirectory() as tmpdir:
            ofm_logging.configure_logging(tmpdir)
            assert len(caplog.records) == 1
            # Check OFM logger is added even if the file logger couldn't be.
            root_logger = logging.getLogger()
            assert ofm_logging.OFM_HANDLER in root_logger.handlers


def test_making_log_dir(caplog):
    """Check that configure_logging will make a dir if needed."""
    # Reset handler at start of test
    ofm_logging.OFM_HANDLER = ofm_logging.OFMHandler()
    with caplog.at_level(logging.WARNING):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "new_dir")
            assert not os.path.isdir(log_dir)
            ofm_logging.configure_logging(log_dir)
            assert len(caplog.records) == 0
            assert os.path.isdir(log_dir)


def test_max_logs():
    """Proclaim that only the most recent 250 logs are stored in memory."""
    # Reset handler at start of test
    ofm_logging.OFM_HANDLER = ofm_logging.OFMHandler()
    with tempfile.TemporaryDirectory() as tmpdir:
        ofm_logging.configure_logging(tmpdir)
        # But I would log five hundred times.
        for i in range(500):
            logging.info("log %s", i)
        logs = ofm_logging.OFM_HANDLER.log_history.split("\n")
        assert len(logs) == 250
        assert logs[0].endswith("log 250")
        assert logs[-1].endswith("log 499")
        # And I would log five hundred more.
        for i in range(500):
            logging.info("log %s", 500 + i)
        # Just to be the test who logged a thousand times to check your hand-el-or!
        logs = ofm_logging.OFM_HANDLER.log_history.split("\n")
        assert len(logs) == 250
        assert logs[0].endswith("log 750")
        assert logs[-1].endswith("log 999")


def test_ofm_handler_ignores_uvicorn_access():
    """Check uvicorn.access logs are ignored by custom handler.

    The uvicorn.access logger logs every time an endpoint is triggered.
    """
    # Reset handler at start of test
    ofm_logging.OFM_HANDLER = ofm_logging.OFMHandler()
    with tempfile.TemporaryDirectory() as tmpdir:
        ofm_logging.configure_logging(tmpdir)
        logs = ofm_logging.OFM_HANDLER.log_history.split("\n")
        starting_len = len(logs)
        logging.info("Root 1")
        uvicorn_logger = logging.getLogger("uvicorn.access")
        for i in range(500):
            uvicorn_logger.info("Uvicorn log %s", i)
        logging.info("Root 2")
        logs = ofm_logging.OFM_HANDLER.log_history.split("\n")
        assert len(logs) == starting_len + 2
        assert logs[starting_len].endswith("Root 1")
        assert logs[-1].endswith("Root 2")


def test_server_responses():
    """Check that the FastAPI responses from the server are as expected.

    * retrieve_log() -> PlainTextResponse containing the last 250 logs separated by
        a new line
    * retrieve_log_from_file() -> All the logs from the log file.
    """
    # Reset handler at start of test
    ofm_logging.OFM_HANDLER = ofm_logging.OFMHandler()
    with tempfile.TemporaryDirectory() as tmpdir:
        ofm_logging.configure_logging(tmpdir)
        for i in range(500):
            logging.info("log %s", i)
        log_response = ofm_logging.retrieve_log()
        assert isinstance(log_response, PlainTextResponse)
        logs = log_response.body.decode().split("\n")
        assert len(logs) == 250
        file_log_response = ofm_logging.retrieve_log_from_file()
        assert isinstance(file_log_response, PlainTextResponse)
        file_logs = file_log_response.body.decode().split("\n")
        assert len(file_logs) > 500


def test_server_response_with_no_log_file():
    """Check that an HTTP exception is raised if logging isn't configured."""
    # Reset handler at start of test
    ofm_logging.OFM_HANDLER = ofm_logging.OFMHandler()
    # Also Reset log file global
    ofm_logging.OFM_LOG_FILE = None
    with pytest.raises(HTTPException) as excinfo:
        ofm_logging.retrieve_log_from_file()
    assert excinfo.value.status_code == 500


def test_server_response_with_no_log_dir():
    """Check that an HTTP exception is raised if the log file cannot be accessed."""
    ofm_logging.OFM_HANDLER = ofm_logging.OFMHandler()
    with tempfile.TemporaryDirectory() as tmpdir:
        ofm_logging.configure_logging(tmpdir)
        for i in range(500):
            logging.info("log %s", i)
        file_log_response = ofm_logging.retrieve_log_from_file()
        assert isinstance(file_log_response, PlainTextResponse)
    # Close and delete the log folder, this should create an error.
    with pytest.raises(HTTPException) as excinfo:
        ofm_logging.retrieve_log_from_file()
    assert excinfo.value.status_code == 500
