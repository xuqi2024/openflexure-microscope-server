#!/usr/bin/env python
from flask import Flask
from typing import List, Optional, Tuple

from labthings import LabThing
from openflexure_microscope.api import openapi
from openflexure_microscope.api.app.fallback import create_fallback_app_and_labthing

# `logging_configuration` performs log file setup as an import side-effect
# The `logging` module is the one from the standard library
from openflexure_microscope.api.logging_configuration import log_level, logging
from openflexure_microscope.paths import OPENFLEXURE_VAR_PATH
from openflexure_microscope.utilities import ConfigurableComponentFailedToLoad

from .implementation import create_app_and_labthing, load_hardware_and_extensions
from .reloader import AppReloader
from .fallback import create_fallback_app_and_labthing

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
    try:
        api_microscope, extensions = load_hardware_and_extensions()
        return create_app_and_labthing(api_microscope, extensions)
    except ConfigurableComponentFailedToLoad as e:
        print("")
        print("****** The OpenFlexure Microscope cannot start *****")
        print("")
        print("This may be fixable by altering your configuration.")
        print("Errors are summarised below:")
        print(e.loaded_components_and_errors)
        print("Starting fallback server to display the error...")
        return create_fallback_app_and_labthing(e)


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
