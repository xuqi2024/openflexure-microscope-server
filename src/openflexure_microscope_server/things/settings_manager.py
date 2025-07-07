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
import labthings_fastapi as lt


def thing_server_from_request(request: Request) -> lt.ThingServer:
    return lt.find_thing_server(request.app)


ThingServerDep = Annotated[lt.ThingServer, Depends(thing_server_from_request)]


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


class SettingsManager(lt.Thing):
    external_metadata = lt.ThingSetting(
        initial_value={},
        model=Mapping,
        description="External metadata stored in the server's settings",
    )

    external_metadata_in_state = lt.ThingSetting(
        initial_value=[],
        model=Sequence[str],
        description='A list of strings that are included in the "state" metadata',
    )

    @lt.thing_action
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
        self.external_metadata = metadata

    @lt.thing_action
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
        self.external_metadata = metadata

    _microscope_id: Optional[str] = None

    @lt.thing_setting
    def microscope_id(self) -> UUID:
        """A unique identifier for this microscope"""
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
        """Metadata summarising the current state of all Things in the server"""
        return metadata_getter()

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
