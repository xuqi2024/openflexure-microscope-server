import copy
import logging
from functools import wraps


def clean_rule(rule: str):
    while rule[0] == "/":
        rule = rule[1:]
    return f"{rule}"


def build_gui_from_dict(gui_description, extension_object):
    # Make a working copy of GUI description
    api_gui = copy.deepcopy(gui_description)

    # Expand shorthand routes into full relative URLs
    if "forms" in gui_description and isinstance(api_gui["forms"], list):
        for form in api_gui["forms"]:
            # Clean leading slashes from rule
            if "route" in form:
                form["route"] = clean_rule(form["route"])
            # Match rule in extension object
            if "route" in form and form["route"] in extension_object._rules.keys():
                form["route"] = extension_object._rules[form["route"]]["rule"]
            else:
                logging.warn(
                    "No valid expandable route found for {}".format(form["route"])
                )

    # Inject extension information
    api_gui["id"] = extension_object.name
    api_gui["version"] = extension_object.version
    return api_gui


def build_gui_from_func(func, extension_object):
    @wraps(func)
    def wrapped(*args, **kwargs):
        return build_gui_from_dict(func(*args, **kwargs), extension_object)

    return wrapped


def build_gui(gui_description, extension_object):
    # If given a function that generates a GUI dictionary
    if callable(gui_description):
        # Wrap in the route expander
        return build_gui_from_func(gui_description, extension_object)
    # If given a dictionary directly
    elif isinstance(gui_description, dict):
        # Build a GUI generator function
        def gui_description_func():
            return gui_description

        # Wrap in the route expander
        return build_gui_from_func(gui_description_func, extension_object)
    else:
        raise RuntimeError("GUI description must be a function or a dictionary")
