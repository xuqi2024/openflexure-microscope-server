"""
OpenFlexure Microscope system control Thing

This module defines a Thing that can shut down or restart the host computer.
"""

import subprocess
import os
from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from pydantic import BaseModel


class CommandOutput(BaseModel):
    output: str
    error: str


class SystemControlThing(Thing):
    """
    Attempt to shutdown the device
    """

    @thing_action
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

    @thing_property
    def is_raspberrypi() -> bool:
        """
        Checks if we are running on a Raspberry Pi.
        """
        return os.path.exists("/usr/bin/raspi-config")

    @thing_action
    def reboot(self) -> CommandOutput:
        """Attempt to reboot the device"""
        p = subprocess.Popen(
            ["sudo", "shutdown", "-r", "now"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        out, err = p.communicate()
        return CommandOutput(output=out, error=err)
