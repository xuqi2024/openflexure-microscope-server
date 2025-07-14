"""OpenFlexure System.

A module to control the underlying microscope system and to expose information about
the microscope, server, and thing states to the web API.
"""

from collections.abc import Mapping
from socket import gethostname
from typing import Optional
from uuid import UUID, uuid4
import subprocess
import os
from signal import SIGTERM
import time

from pydantic import BaseModel

import labthings_fastapi as lt

from openflexure_microscope_server.utilities import VersionData, robust_version_strings


class CommandOutput(BaseModel):
    """A pydantic model passing the STDOUT and STDERR from a subprocess over HTTP."""

    output: str
    error: str


class OpenFlexureSystem(lt.Thing):
    """Describe and control the OpenFlexure system.

    This Thing:

    * Exposes information about the Microscope, Server, and Thing states to the web
        API.
    * Controls the underlying OS on the Raspberry Pi allowing shutdown and restarting
        of the system.
    """

    _microscope_id: Optional[str] = None

    @lt.thing_setting
    def microscope_id(self) -> UUID:
        """A unique identifier for this microscope."""
        if self._microscope_id is None:
            self._microscope_id = str(uuid4())
        return UUID(self._microscope_id)

    @microscope_id.setter
    def microscope_id(self, uuid: UUID):
        # TODO make read only but still settable from disk
        self._microscope_id = uuid

    @lt.thing_property
    def hostname(self) -> str:
        """The hostname of the microscope, as reported by its operating system."""
        return gethostname()

    _version_data: Optional[VersionData] = None

    @lt.thing_property
    def version_data(self) -> VersionData:
        """The version string and version source for the server.

        The source may be a commit hash if installed from git. "TOML" if installed from
        source, or "Dist" if installed from a distribution package.

        If the version or its source cannot be determined an error will be Logged.
        """
        # Don't save as a setting as it may change. Get the version string the first
        # time the property is requested this boot.
        if self._version_data is None:
            self._version_data = robust_version_strings()
        return self._version_data

    @lt.thing_property
    def is_raspberrypi(self) -> bool:
        """Return True if running on a Raspberry Pi."""
        return os.path.exists("/usr/bin/raspi-config")

    @lt.thing_action
    def shutdown(self) -> CommandOutput:
        """Attempt to shutdown the device."""
        if not self.is_raspberrypi:
            os.kill(os.getpid(), SIGTERM)
            time.sleep(0.5)
            # If this line is reached then the server did not shut down!
            return CommandOutput(
                output="",
                error="Shutdown command sent to server process, but the server has not shutdown.",
            )

        # On a Raspberry Pi
        p = subprocess.Popen(
            ["sudo", "shutdown", "-h", "now"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        out, err = p.communicate()
        return CommandOutput(output=out, error=err)

    @lt.thing_action
    def reboot(self) -> CommandOutput:
        """Attempt to reboot the device."""
        if not self.is_raspberrypi:
            return CommandOutput(
                output="",
                error="Restart is only available on Raspberry Pi.",
            )

        p = subprocess.Popen(
            ["sudo", "shutdown", "-r", "now"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        out, err = p.communicate()
        return CommandOutput(output=out, error=err)

    @lt.thing_action
    def get_things_state(self, metadata_getter: lt.deps.GetThingStates) -> Mapping:
        """Metadata summarising the current state of all Things in the server."""
        return metadata_getter()

    @property
    def thing_state(self) -> Mapping:
        """Summary metadata describing the current state of the Thing."""
        return {
            "hostname": self.hostname,
            "microscope-uuid": str(self.microscope_id),
            "version": self.version_data.version,
            "version_source": self.version_data.version_source,
        }
