"""Test the SmartScanThing *without* connecting it to a LabThings Server.

By testing without connecting to the LabThings server it is possible to
directly poll any properties and to start any methods.

Any methods with LabThings dependency injections will require dependencies
to be passed in manually. Rather than passing in real LabThings clients
it is possible to create test objects that mock these clients. Thus, entirely
isolating one Thing for testing, at the expense of needing to create detailed
mock objects.

For these tests to reliably represent real behaviour the mock Things will need to
be tested for matching signatures with dynamically generated clients.
"""

from typing import Callable, Optional
import tempfile
import os
import shutil
import logging

from fastapi import HTTPException
import pytest

from openflexure_microscope_server.things.smart_scan import (
    SmartScanThing,
    ScanNotRunningError,
)

from .mock_things.mock_csm import MockCSMThing
from .mock_things.mock_autofocus import MockAutoFocusThing
from .mock_things.mock_stage import MockStageThing
from .mock_things.mock_background_detect import MockBackgroundDetectThing

# A global logger to pass in as an Invocation Logger
LOGGER = logging.getLogger("mock-invocation_logger")

# Use our own dir in the root temp dir not a dynamically generated one so we
# have some control of when it is deleted
SCAN_DIR = os.path.join(tempfile.gettempdir(), "scans")


def _clear_scan_dir() -> None:
    """Delete the scan dir."""
    if os.path.exists(SCAN_DIR):
        shutil.rmtree(SCAN_DIR)


@pytest.fixture
def smart_scan_thing():
    """Return a smart scan thing as a fixture."""
    return SmartScanThing(SCAN_DIR)


def test_initial_properties(smart_scan_thing):
    """Check the initial values of properties.

    Test properties of SmartScanThing are available without a ThingServer
    and return expected default values.
    """
    assert smart_scan_thing._scan_dir_manager.base_dir == SCAN_DIR
    assert smart_scan_thing.latest_scan_name is None


def test_inaccessible_scan_methods(smart_scan_thing):
    """Test that method with @_scan_running decorator is inaccessible.

    The @_scan_running decorator makes these functions inaccessible unless
    a scan is running.
    """
    with pytest.raises(ScanNotRunningError):
        smart_scan_thing._run_scan()
    with pytest.raises(ScanNotRunningError):
        smart_scan_thing._manage_stitching_threads()


def test_private_delete_scan(smart_scan_thing, caplog):
    """Test the private _delete_scan method deletes directories or warns if it can't."""
    _clear_scan_dir()
    with caplog.at_level(logging.INFO):
        fake_scan_name = "fake_scan_0001"
        fake_scan_path = os.path.join(SCAN_DIR, fake_scan_name)

        # Make the outer scan dir, but not the one to delete
        os.makedirs(SCAN_DIR)
        # Attempt to delete the fake scan. Expect it to fail and provide a warning
        deleted = smart_scan_thing._delete_scan(fake_scan_name, LOGGER)
        assert not deleted
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert caplog.records[0].name == "mock-invocation_logger"

        # Make a dir for the fake scan and delete it.
        os.makedirs(fake_scan_path)
        assert os.path.exists(fake_scan_path)
        deleted = smart_scan_thing._delete_scan(fake_scan_name, LOGGER)
        assert not os.path.exists(fake_scan_path)
        assert deleted
        # Check no extra logs generated
        assert len(caplog.records) == 1


def test_public_delete_scan(smart_scan_thing, caplog):
    """Test the delete_scan API call deletes directories or warns if it can't."""
    _clear_scan_dir()
    with caplog.at_level(logging.INFO):
        fake_scan_name = "fake_scan_0001"
        fake_scan_path = os.path.join(SCAN_DIR, fake_scan_name)

        # Make the outer scan dir, but not the one to delete
        os.makedirs(SCAN_DIR)

        # Attempt to delete the fake scan. Expect it to fail
    with pytest.raises(HTTPException) as exc_info:
        smart_scan_thing.delete_scan(fake_scan_name, LOGGER)
        # Should raise a 400 error if the scan doesn't exist, not a 404 as the server
        # was not expecting to receive the scan files
        assert exc_info.value.status_code == 400
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert caplog.records[0].name == "mock-invocation_logger"

        # Make a dir for the fake scan and delete it.
        os.makedirs(fake_scan_path)
        assert os.path.exists(fake_scan_path)
        smart_scan_thing.delete_scan(fake_scan_name, LOGGER)
        assert not os.path.exists(fake_scan_path)
        # Check no extra logs generated
        assert len(caplog.records) == 1


def test_delete_all_scans(smart_scan_thing, caplog):
    """Check the delete_all_scan API really does delete all the scans."""
    _clear_scan_dir()
    with caplog.at_level(logging.INFO):
        fake_scan_names = [
            "fake_scan_0001",
            "fake_scan_0002",
            "fake_scan_0003",
            "fake_scan_0004",
        ]
        for fake_scan_name in fake_scan_names:
            fake_scan_path = os.path.join(SCAN_DIR, fake_scan_name)
            os.makedirs(fake_scan_path)
            assert os.path.exists(fake_scan_path)
        smart_scan_thing.delete_all_scans(LOGGER)
        for fake_scan_name in fake_scan_names:
            fake_scan_path = os.path.join(SCAN_DIR, fake_scan_name)
            assert not os.path.exists(fake_scan_path)
        # No logs generated
        assert len(caplog.records) == 0


def _run_only_outer_scan(adjust_initial_state: Optional[Callable] = None):
    """Create a subclass of SmartScanThing to mock _run_scan and run sample_scan.

    This should do all the set up for a scan, move into the mocked
    _run_scan method where this can be tested. Once this is done
    the final scan behaviour can be tested too.

    adjust_initial_state is a callable which accepts the mocked smart scan thing
    as the only variable. It can be used to adjust the initial state of the test


    This seems hard to do with a fixture so it is being done with a private
    function
    """
    # cancel handle shouldn't be used. Set to arbitrary value for checking
    cancel_mock = 1  # not called
    af_mock = MockAutoFocusThing()
    stage_mock = MockStageThing()
    cam_mock = 4  # not called
    meta_mock = 5  # not called
    csm_mock = MockCSMThing()
    bkgrnd_det_mock = MockBackgroundDetectThing()

    class MockedSmartScanThing(SmartScanThing):
        """Mocked version of SmartScanThing with a patched _run_scan method."""

        # Counter for checking functions were called
        mock_call_count = {"_run_scan": 0}

        def _run_scan(self):
            self.mock_call_count["_run_scan"] += 1

            """Check scan vars are set up as expected"""
            assert not self._scan_lock.acquire(timeout=0.1)
            assert self._cancel is cancel_mock
            assert self._scan_logger is LOGGER
            assert self._autofocus is af_mock
            assert self._stage is stage_mock
            assert self._cam is cam_mock
            assert self._metadata_getter is meta_mock
            assert self._csm is csm_mock
            assert self._background_detect is bkgrnd_det_mock
            assert self._capture_thread is None
            assert self._scan_images_taken == 0

    # mock smart scan thing
    mock_ss_thing = MockedSmartScanThing(SCAN_DIR)

    if adjust_initial_state is not None:
        adjust_initial_state(mock_ss_thing)

    exec_info = None
    try:
        mock_ss_thing.sample_scan(
            cancel=cancel_mock,  # Shouldn't be used, can be checked
            logger=LOGGER,
            autofocus=af_mock,
            stage=stage_mock,
            cam=cam_mock,
            metadata_getter=meta_mock,
            csm=csm_mock,
            background_detect=bkgrnd_det_mock,
            scan_name="FooBar",
        )
    except Exception as e:
        exec_info = e

    assert mock_ss_thing._scan_lock.acquire(timeout=0.1)
    mock_ss_thing._scan_lock.release()
    assert mock_ss_thing._cancel is None
    assert mock_ss_thing._scan_logger is None
    assert mock_ss_thing._autofocus is None
    assert mock_ss_thing._stage is None
    assert mock_ss_thing._cam is None
    assert mock_ss_thing._metadata_getter is None
    assert mock_ss_thing._csm is None
    assert mock_ss_thing._background_detect is None
    assert mock_ss_thing._capture_thread is None
    assert mock_ss_thing._scan_images_taken is None

    # Return the mock thing for further state testing, and the
    # exec_info of any uncaught exceptions that were raised
    return mock_ss_thing, exec_info


def test_outer_scan():
    """Test setup and teardown of the scan."""
    mock_ss_thing, exec_info = _run_only_outer_scan()
    assert exec_info is None
    # Checked the mocked _run_scan was run exactly once
    assert mock_ss_thing.mock_call_count["_run_scan"] == 1


def test_outer_scan_wo_sample_skip():
    """Test setup and teardown of the scan."""

    def _set_skip_background(mock_ss_thing):
        # As the Thing is not connected to a server we set the setting via the internal
        # __dict__ to avoid triggering property emits that require a server
        mock_ss_thing.__dict__["skip_background"] = False

    mock_ss_thing, exec_info = _run_only_outer_scan(_set_skip_background)

    assert exec_info is None
    # Checked the mocked _run_scan was run exactly once
    assert mock_ss_thing.mock_call_count["_run_scan"] == 1
