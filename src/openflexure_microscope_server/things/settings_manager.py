"""OpenFlexure Settings Management.

This module provides some settings management across the other Things, and
for code that currently lives in clients but needs to persist settings on
the server.
"""

from collections.abc import Mapping
from socket import gethostname
from typing import Optional
from uuid import UUID, uuid4

import labthings_fastapi as lt


class SettingsManager(lt.Thing):
    """Provides functionality to other Things about the current server state.

    The SettingsManager is used to get information the microscope ID, the hostname
    and the state of other Things.
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
        }
