"""
OpenFlexure Microscope system control Thing

This module defines a Thing that can shut down or restart the host computer.
"""

import subprocess
import os
import labthings_fastapi as lt
from pydantic import BaseModel


class CommandOutput(BaseModel):
    output: str
    error: str


class SystemControlThing(lt.Thing):
    """
    Attempt to shutdown the device
    """

    @lt.thing_action
    def shutdown(self) -> CommandOutput:
        """
        Attempt to shutdown the device
        """
        p = subprocess.Popen(
            ["sudo", "shutdown", "-h", "now"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        out, err = p.communicate()
        return CommandOutput(output=out, error=err)

    @lt.thing_property
    def is_raspberrypi() -> bool:
        """
        Checks if we are running on a Raspberry Pi.
        """
        return os.path.exists("/usr/bin/raspi-config")

    @lt.thing_action
    def reboot(self) -> CommandOutput:
        """Attempt to reboot the device"""
        p = subprocess.Popen(
            ["sudo", "shutdown", "-r", "now"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        out, err = p.communicate()
        return CommandOutput(output=out, error=err)
