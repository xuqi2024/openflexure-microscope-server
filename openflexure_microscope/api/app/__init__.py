#!/usr/bin/env python
import logging
import threading
import time

import atexit
import pkg_resources
from flask import abort, Flask
from flask_cors import CORS, cross_origin
from labthings import create_app, LabThing
from labthings.extensions import BaseExtension
from typing import List, Tuple, Optional

from openflexure_microscope.api import openapi

# `logging_configuration` performs log file setup as an import side-effect
from openflexure_microscope.api.logging_configuration import log_level
from openflexure_microscope.api.utilities import list_routes
from openflexure_microscope.api.v2 import views
from openflexure_microscope.extensions.load import load_extensions
from openflexure_microscope.json import JSONEncoder
from openflexure_microscope.microscope import Microscope
from openflexure_microscope.paths import (
    OPENFLEXURE_VAR_PATH,
)
from .implementation import load_hardware_and_extensions, create_app_and_labthing
from .reloader import AppReloader

# Log server paths being used
logging.info("Running with data path %s", OPENFLEXURE_VAR_PATH)


def create_app_and_labthing_with_fallback() -> Tuple[Flask, LabThing]:
    """Set up the labthing, and run a fallback server on certain errors.
    
    If the microscope is misconfigured (e.g. it expects missing hardware)
    then `load_hardware_and_extensions` will fail.  In that case, rather
    than crash completely, we log the error and start a fallback server,
    which will make it clear what's wrong to anyone looking at the HTTP
    API.
    """
    api_microscope, extensions = load_hardware_and_extensions()
    return create_app_and_labthing(api_microscope, extensions)


# This object will work like an application, but it's wrapped in a hook
# that allows us to reload the app without restarting Python.
app = AppReloader(create_app_and_labthing_with_fallback)


# Expose a function at module level that triggers a reload.
restart = app.request_reload


def ofm_serve():
    # Start a debug server
    from labthings import Server

    logging.info("Starting OpenFlexure Microscope Server...")
    server: Server = Server(app)
    server.run(
        host="0.0.0.0", port=5000, debug=log_level == logging.DEBUG, zeroconf=True
    )


def generate_openapi():
    """Generate an OpenAPI description and save as a file"""
    openapi.generate_openapi_from_labthing(app.labthing)


# Start the app if the module is run directly
if __name__ == "__main__":
    ofm_serve()
