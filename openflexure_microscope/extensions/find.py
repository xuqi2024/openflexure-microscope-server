"""Code to find extension classes."""

import logging

from pkg_resources import EntryPoint
from typing import List

# this is importlib.metadata, with a workaround for python<3.8
from openflexure_microscope.utilities import metadata


def list_entry_points(group_name: str) -> List[EntryPoint]:
    """Return a list of entry points in a particular group.
    
    This uses the importlib metadata mechanism to enumerate entry points
    declared in installed packages.  By default, it will list all entry
    points belonging to the group for OFM extensions.

    A list of EntryPoint objects is returned, which may be empty.
    """
    try:
        return metadata.entry_points()[group_name]  # type: ignore[attr-defined]
    except KeyError:
        # A KeyError means there are no entry points in the specified group
        return []


def list_entry_point_values(group_name: str):
    """A list of entry point values, as strings, for the given group."""
    entry_points = list_entry_points(group_name)
    return [p.value for p in entry_points]  # type: ignore[attr-defined]


def find_entry_point(value: str, group_name: str) -> EntryPoint:
    """Load an entry point, given its value.
    
    The argument is an entry point value, i.e. a string in
    `module.submodule:ClassName` form.  If the value corresponds to an
    available entry point, that entry point will be included
    in the returned list.  The entry point must be found in the
    group specified by `group_name`, by default the group for LabThings
    extensions.

    The list of entry points is retrieved fresh every time this function
    is run.  That costs a few milliseconds, but as it's only run a few
    times at start-up, we are prioritising simple, reliable code over 
    super high performance.
    """
    available_eps = list_entry_points(group_name=group_name)
    matching_eps = [p for p in available_eps if p.value == value]  # type: ignore[attr-defined]
    if len(matching_eps) == 0:
        raise ValueError(
            f"Tried to load entry point {value} from group "
            f"{group_name}, but it does not appear to be present. "
            "If the module exists on your system, it may not be "
            "installed correctly, or may not declare the entry point."
        )
    if len(matching_eps) > 1:
        logging.warning(
            f"{value} appears more than once in the list of entry "
            f"points for group {group_name}.  This may indicate "
            "something is wrong with your Python environment"
        )
    return matching_eps[0]
