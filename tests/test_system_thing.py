"""Test the OpenFlexureSystem Thing *without* connecting it to a LabThings Server."""

import os
from signal import SIGTERM
from uuid import UUID

from openflexure_microscope_server.things import system
from openflexure_microscope_server.utilities import VersionData, robust_version_strings


def _is_raspberrypi() -> bool:
    """Check if the machine running the test is a Raspberry Pi.

    This information is needed to check if the ``is_raspberrypi`` property of the Thing
    is correct. This is implemented in a different way to in the main code.
    """
    # Check if the file specifying the Raspberry Pi model exists
    if not os.path.isfile("/proc/device-tree/model"):
        return False
    with open("/proc/device-tree/model", "r", encoding="utf-8") as model_file:
        model_name = model_file.read()
    return "Raspberry Pi" in model_name


def test_is_raspberry():
    """Check the thing property reports whether this is a Raspberry Pi correctly."""
    assert system.OpenFlexureSystem().is_raspberrypi == _is_raspberrypi()


def test_version_data():
    """Check VersionData is returned.

    The content of robust_version_strings() is tested elsewhere.
    """
    system_thing = system.OpenFlexureSystem()
    data = system_thing.version_data
    assert isinstance(data, VersionData)
    assert data == robust_version_strings()

    fake_data = VersionData(version="fake", version_source="fake")
    system_thing._version_data = fake_data
    data = system_thing.version_data
    assert data == fake_data


def test_hostname(mocker):
    """Check the hostname matches what socket.gethostname() returns."""
    mock_gethostname = mocker.patch("socket.gethostname", return_value="foobar")
    system_thing = system.OpenFlexureSystem()
    assert system_thing.hostname == "foobar"
    mock_gethostname.assert_called_once_with()


def test_microscope_id():
    """Check the microscope UUID is a valid UUID and doesn't change when read again."""
    system_thing = system.OpenFlexureSystem()
    microscope_id = system_thing.microscope_id
    assert isinstance(microscope_id, UUID)
    assert microscope_id == system_thing.microscope_id


def test_thing_state(mocker):
    """Check the thing state contains version data, hostname, and a UUID string."""
    mocker.patch("socket.gethostname", return_value="foobar")
    version_data = robust_version_strings()
    system_thing = system.OpenFlexureSystem()
    state_dict = system_thing.thing_state
    assert state_dict["hostname"] == "foobar"
    # Check the UUID in the dictionary is a string
    assert isinstance(state_dict["microscope-uuid"], str)
    # Check uuid string can be converted to valid UUID
    UUID(state_dict["microscope-uuid"])
    assert state_dict["version"] == version_data.version
    assert state_dict["version_source"] == version_data.version_source


class MockPiSystem(system.OpenFlexureSystem):
    """A OpenFlexureSystem Thing that always claims to be a Raspberry Pi."""

    is_raspberrypi: bool = True


class MockNonPiSystem(system.OpenFlexureSystem):
    """A OpenFlexureSystem Thing that never claims to be a Raspberry Pi."""

    is_raspberrypi: bool = False


def test_pi_shutdown(mocker):
    """Check that on a Pi will receive the correct shutdown command."""
    # Check the shutdown command is as expected.
    assert system.SHUTDOWN_CMD == ["sudo", "shutdown", "-h", "now"]
    # Mock the shutdown command as we don't want to shutdown when running tests.
    mocker.patch.object(system, "SHUTDOWN_CMD", new=["echo", "shutdown"])
    # Call shutdown on a MockPiSystem
    system_thing = MockPiSystem()
    result = system_thing.shutdown()

    # Check the result of the echo mock command was returned
    assert result.output.strip() == "shutdown"
    assert result.error.strip() == ""


def test_pi_reboot(mocker):
    """Check that on a Pi will receive the correct reboot command."""
    # Check the reboot command is as expected.
    assert system.REBOOT_CMD == ["sudo", "shutdown", "-r", "now"]
    # Mock the reboot command as we don't want to reboot when running tests.
    mocker.patch.object(system, "REBOOT_CMD", new=["echo", "restart"])
    # Call reboot on a MockPiSystem
    system_thing = MockPiSystem()
    result = system_thing.reboot()

    # Check the result of the echo mock command was returned
    assert result.output.strip() == "restart"
    assert result.error.strip() == ""


def test_non_pi_shutdown(mocker):
    """Check that a server not on a pi runs os.kill when asked to shutdown.

    It should do this instead of running the shutdown command in a subprocess.
    """
    # Mock os.kill
    mock_kill = mocker.patch("os.kill")
    # Get this subprocess
    pid = os.getpid()
    system_thing = MockNonPiSystem()
    result = system_thing.shutdown()

    # Check it tried to kill this process with SIGTERM
    mock_kill.assert_called_once_with(pid, SIGTERM)
    # Check output is an appropriate error message (that we have not shut down!)
    assert result.output.strip() == ""
    assert "but the server has not shutdown" in result.error


def test_non_pi_reboot():
    """Check that a server not on a pi refuses to restart."""
    system_thing = MockNonPiSystem()
    result = system_thing.reboot()

    # Check output is an appropriate error message
    assert result.output.strip() == ""
    assert result.error.strip() == "Restart is only available on Raspberry Pi."
