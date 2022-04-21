#!/usr/bin/env python
"""
This is, for the moment, the top-level OFM server file.  Its imports are
deliberately spartan, because we're now explicitly configuring things like
logging and paths, and we need to do that before importing the rest of
the server.

Improving this so modules are less interdependent is a work in progress.
For now, we must simply make sure to call `initialise_paths` and
`configure_logging` before importing any modules that depend on
paths being set at import-time.
"""
from typing import List, Optional, Tuple

from flask import Flask
from labthings import LabThing
import logging
import os


from openflexure_microscope.api.logging_configuration import (
    configure_logging,
    root_debug,
)
from openflexure_microscope.config import (
    add_config_args,
    load_config,
    default_config,
    MicroscopeConfig,
)
from openflexure_microscope.extensions.load import (
    load_components,
    ConfigurableComponentFailedToLoad,
)
from openflexure_microscope.paths import initialise_paths, OpenFlexurePaths


def create_app_and_labthing_with_fallback() -> Tuple[Flask, LabThing]:
    """Set up the labthing, and run a fallback server on certain errors.
    
    If the microscope is misconfigured (e.g. it expects missing hardware)
    then `load_hardware_and_extensions` will fail.  In that case, rather
    than crash completely, we log the error and start a fallback server,
    which will make it clear what's wrong to anyone looking at the HTTP
    API.
    """
    config, paths = initialise_and_configure()

    try:
        components = load_components(config)
        from .implementation import create_app_and_labthing

        return create_app_and_labthing(components, paths)
    except ConfigurableComponentFailedToLoad as e:
        print("")
        print("****** The OpenFlexure Microscope cannot start *****")
        print("")
        print("This may be fixable by altering your configuration.")
        print("Errors are summarised below:")
        print(e.summary)
        from .fallback import create_fallback_app_and_labthing

        return create_fallback_app_and_labthing(config, e)


def initialise_and_configure() -> Tuple[MicroscopeConfig, OpenFlexurePaths]:
    try:
        config: MicroscopeConfig = load_config()
    except FileNotFoundError:
        logging.warning("No config file found, using defaults")
        config: MicroscopeConfig = default_config()
    paths = initialise_paths(openflexure_dir=config.openflexure_dir)
    configure_logging(paths.logs)
    return config, paths


def ofm_serve():
    # Start a debug server
    from labthings import Server

    app, labthing = create_app_and_labthing_with_fallback()

    server: Server = Server(app)
    server.run(host="0.0.0.0", port=5000, debug=root_debug(), zeroconf=True)


def generate_openapi():
    """Generate an OpenAPI description and save as a file"""
    from openflexure_microscope.api import openapi

    openapi.generate_openapi_from_labthing(app.labthing)


# Start the app if the module is run directly
if __name__ == "__main__":
    ofm_serve()
