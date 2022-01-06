import errno
import logging
import os
from typing import Union

from flask import Blueprint, Flask, current_app, url_for
from flask.views import View

from . import gui

__all__ = [
    "gui",
    "view_class_from_endpoint",
    "blueprint_for_module",
    "get_bool",
    "list_routes",
    "create_file",
]


def view_class_from_endpoint(endpoint: str) -> View:
    return current_app.view_functions[endpoint].view_class


def blueprint_for_module(module_name: str, api_ver: int = 2, suffix: str = ""):
    return Blueprint(
        blueprint_name_for_module(module_name, api_ver=api_ver, suffix=suffix),
        module_name,
    )


def blueprint_name_for_module(module_name: str, api_ver: int = 2, suffix: str = ""):
    bp_name = module_name.split(".")[-1]
    return f"v{api_ver}_{bp_name}_blueprint{suffix}"


def get_bool(get_arg: Union[bool, str]):
    """Convert GET request argument string to a Python bool"""
    if isinstance(get_arg, bool):
        return get_arg
    elif get_arg == "true" or get_arg == "True" or get_arg == "1":
        return True
    else:
        return False


def list_routes(app: Flask):
    output = {}
    for rule in app.url_map.iter_rules():

        options = {}
        for arg in rule.arguments:
            options[arg] = "[{0}]".format(arg)

        endpoint = rule.endpoint
        methods = list(rule.methods)
        url = url_for(rule.endpoint, **options)
        line = {"endpoint": endpoint, "methods": methods}
        output[url] = line

    return output


def create_file(config_path: str):
    if not os.path.exists(os.path.dirname(config_path)):
        try:
            os.makedirs(os.path.dirname(config_path))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
