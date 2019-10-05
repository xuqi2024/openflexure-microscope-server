import copy
import operator
from collections import abc
from functools import reduce
from contextlib import contextmanager


@contextmanager
def set_properties(obj, **kwargs):
    """A context manager to set, then reset, certain properties of an object.

    The first argument is the object, subsequent keyword arguments are properties
    of said object, which are set initially, then reset to their previous values.
    """
    saved_properties = {}
    for k in kwargs.keys():
        try:
            saved_properties[k] = getattr(obj, k)
        except AttributeError:
            print(
                "Warning: could not get {} on {}.  This property will not be restored!".format(
                    k, obj
                )
            )
    for k, v in kwargs.items():
        setattr(obj, k, v)
    try:
        yield
    finally:
        for k, v in saved_properties.items():
            setattr(obj, k, v)


def axes_to_array(
    coordinate_dictionary, axis_keys=("x", "y", "z"), base_array=None, asint=True
):
    """Takes key-value pairs of a JSON value, and maps onto an array"""
    # If no base array is given
    if not base_array:
        # Create an array of zeros
        base_array = [0] * len(axis_keys)
    else:
        # Create a copy of the passed base_array
        base_array = copy.copy(base_array)

    # Do the mapping
    for axis, key in enumerate(axis_keys):
        if key in coordinate_dictionary:
            base_array[axis] = (
                int(coordinate_dictionary[key]) if asint else coordinate_dictionary[key]
            )

    return base_array


def filter_dict(dictionary: dict, keys: list):
    # Get value by recursively applying getitem
    val = reduce(operator.getitem, keys, dictionary)

    # Create new dictionary by running reduce on key, val pairs
    out = reduce(lambda x, y: {y: x}, reversed(keys), val)

    return out


def entry_by_id(entry_id: str, object_list: list):
    """Return an object from a list, if <object>.id matches id argument."""
    found = None
    for o in object_list:
        if o.id == entry_id:
            found = o
    return found


def recursively_apply(data, func):
    """
    Recursively apply a function to a dictionary, list, array, or tuple

    Args:
        data: Input iterable data
        func: Function to apply to all non-iterable values
    """
    # If the object is a dictionary
    if isinstance(data, abc.Mapping):
        return {key: recursively_apply(val, func) for key, val in data.items()}
    # If the object is iterable but NOT a dictionary or a string
    elif (
        isinstance(data, abc.Iterable)
        and not isinstance(data, abc.Mapping)
        and not isinstance(data, str)
    ):
        return [recursively_apply(x, func) for x in data]
    # if the object is neither a map nor iterable
    else:
        return func(data)
