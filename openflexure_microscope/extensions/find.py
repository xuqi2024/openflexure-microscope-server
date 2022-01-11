"""Code to find extension classes."""

import logging

from openflexure_microscope.utilities import (  # this is importlib.metadata, with a workaround for python<3.8
    metadata,
)

EXTENSION_GROUP_NAME = "openflexure_microscope_extensions"


def extension_entry_points(group_name=EXTENSION_GROUP_NAME):
    """Return a list of entry points in a particular group.
    
    This uses the importlib metadata mechanism to enumerate entry points
    declared in installed packages.  By default, it will list all entry
    points belonging to the group for OFM extensions.

    A list of EntryPoint objects is returned, which may be empty.
    """
    try:
        return metadata.entry_points()[group_name]
    except KeyError:
        return []


def entry_points_from_list(entry_point_values, fail_on_missing=False):
    """Load a list of entry points for extensions
    
    The argument is a list of entry point values, i.e. specified in
    `module.submodule:ClassName` form.  If the value corresponds to an
    available entry point, that entry point will be included
    in the returned list.

    Specifying `fail_on_missing=True` will raise an exception if a
    value is not matched.  The default logs an error but continues
    with other entry points.
    """
    # TODO: deduplicate with utilities:load_entrypoint
    available_eps = extension_entry_points()
    entry_points = []
    for v in entry_point_values:
        matching_eps = [p for p in available_eps if p.value == v]
        if len(matching_eps) == 0:
            logging.error(f"No extension could be found matching '{v}'")
            if fail_on_missing:
                raise ValueError(f"No extension could be found matching '{v}'")
        if len(matching_eps) > 1:
            logging.warning(f"There was more than one entry point for {v}")
        if len(matching_eps) > 0:
            # If the "value" specified corresponds to an installed entry point, load it.
            # NB this will cause the server to fail if an enabled extension can't load
            entry_points.append(matching_eps[0])
    return entry_points
