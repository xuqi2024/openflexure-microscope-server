"""
OpenFlexure Settings Management

This module provides some settings management across the other Things, and
for code that currently lives in clients but needs to persist settings on
the server.
"""

from collections.abc import Mapping
from socket import gethostname
from typing import Annotated, Any, MutableMapping, Optional, Sequence
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException, Request
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.server import find_thing_server, ThingServer
from labthings_fastapi.dependencies.invocation import InvocationLogger


def thing_server_from_request(request: Request) -> ThingServer:
    return find_thing_server(request.app)


ThingServerDep = Annotated[ThingServer, Depends(thing_server_from_request)]


def recursive_update(old_dict: MutableMapping, update: Mapping):
    """Update a dictionary recursively"""
    for k, v in update.items():
        if isinstance(v, Mapping):
            if k in old_dict and isinstance(old_dict[k], MutableMapping):
                recursive_update(old_dict[k], v)
            else:
                old_dict[k] = dict(**v)
        else:
            old_dict[k] = v


def nested_dict_get(data: dict, key: Sequence[str], create=False) -> Any:
    """Index a dict-of-dicts with a sequence of strings"""
    subdict = data
    for k in key:
        if k not in subdict and create:
            subdict[k] = {}
        subdict = subdict[k]
    return subdict


class SettingsManager(Thing):
    @thing_property
    def external_metadata(self) -> Mapping:
        """External metadata stored in the server's settings"""
        return self.thing_settings.get("external_metadata", {})

    @thing_action
    def update_external_metadata(
        self, data: Mapping, key: Optional[str] = None
    ) -> None:
        """Add or replace keys in the external metadata.

        The data supplied will be merged into the existing dictionary
        recursively, i.e. if a key exists, it will be added to rather than
        replaced.

        If a key is supplied, we will treat `data` as being relative to that
        key, i.e. calling this action with `data={"a":1 }, key="foo/bar"` is
        equivalent to calling it with `data={"foo": {"bar": {"a": 1}}}`.
        """
        metadata = self.external_metadata
        subdict = metadata
        # If we're operating only on a part of the dict, make sure
        # that key exists, and find it.
        if key:
            subdict = nested_dict_get(subdict, key.split("/"), create=True)
        recursive_update(subdict, data)
        self.thing_settings["external_metadata"] = metadata

    @thing_action
    def delete_external_metadata(self, key: str) -> None:
        """Delete a key from the stored metadata.

        The key may contain forward slashes, which are understood to separate
        levels of the dictionary - i.e. `'a/c'` will remove the `c` key from a
        dictionary that looks like: `{'a': {'c': 1}, 'b': {'d': 2}}`
        """
        metadata = self.external_metadata
        try:
            subdict = nested_dict_get(metadata, key.split("/")[:-1])
            del subdict[key.split("/")[-1]]
        except KeyError:
            raise HTTPException(
                status_code=404, detail="The specified key '{key}' was not found"
            )
        self.thing_settings["external_metadata"] = metadata

    @thing_property
    def microscope_id(self) -> UUID:
        """A unique identifier for this microscope"""
        if "microscope_id" not in self.thing_settings:
            self.thing_settings["microscope_id"] = str(uuid4())
        return UUID(self.thing_settings["microscope_id"])

    @thing_property
    def hostname(self) -> str:
        """The hostname of the microscope, as reported by its operating system."""
        return gethostname()

    @thing_action
    def get_things_state(self, metadata_getter: GetThingStates) -> Mapping:
        """Metadata summarising the current state of all Things in the server"""
        return metadata_getter()

    @thing_property
    def external_metadata_in_state(self) -> Sequence[str]:
        """A list of strings that are included in the "state" metadata"""
        return self.thing_settings.get("external_metadata_in_state", [])

    @external_metadata_in_state.setter
    def external_metadata_in_state(self, keys: Sequence[str]):
        """Set the keys from external metadata that are returned in state"""
        self.thing_settings["external_metadata_in_state"] = keys

    @property
    def thing_state(self) -> Mapping:
        state = {
            "hostname": self.hostname,
            "microscope-uuid": str(self.microscope_id),
        }
        metadata = self.external_metadata
        for k in self.external_metadata_in_state:
            try:
                kl = k.split("/")
                v = nested_dict_get(metadata, kl)
                subdict = nested_dict_get(state, kl[:-1], create=True)
                subdict[kl[-1]] = v
            except KeyError:
                continue
        return state

    @thing_action
    def save_all_thing_settings(
        self, thing_server: ThingServerDep, logger: InvocationLogger
    ) -> None:
        """Ensure all the Things sync their settings to disk.

        Normally, each Thing has a `thing_settings` attribute that can be
        used to save settings. That dictionary is saved to a JSON file
        when the server shuts down cleanly.

        This action causes all the `thing_settings` dictionaries to be
        saved to files immediately, meaning that settings will not be
        lost in the event of a server crash, power outage, etc.
        """
        for name, thing in thing_server.things.items():
            try:
                if thing._labthings_thing_settings:
                    thing._labthings_thing_settings.write_to_file()
                    logger.info(f"Wrote {name} settings to disk.")
            except PermissionError:
                logger.warning(
                    f"Could not write {name} settings to disk: permission error."
                )
            except FileNotFoundError:
                logger.warning(f"Could not write {name} settings, folder not found")
