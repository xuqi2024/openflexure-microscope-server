#!/usr/bin/env python
import argparse
import atexit
import logging
import time

import os

import pkg_resources
from flask import abort
from flask_cors import CORS, cross_origin
from labthings import create_app
from labthings.extensions import find_extensions

# `logging_configuration` performs log file setup as an import side-effect
from openflexure_microscope.api.logging_configuration import log_level
from openflexure_microscope import extensions
from openflexure_microscope.api.utilities import list_routes
from openflexure_microscope.api.v2 import views
from openflexure_microscope.json import JSONEncoder
from openflexure_microscope.microscope import Microscope
from openflexure_microscope.paths import (
    OPENFLEXURE_EXTENSIONS_PATH,
    OPENFLEXURE_VAR_PATH,
)

from openflexure_microscope.api import openapi


# Log server paths being used
logging.info("Running with data path %s", OPENFLEXURE_VAR_PATH)

# Create the microscope object
api_microscope: Microscope = Microscope()
logging.debug("Restoring captures...")
api_microscope.captures.rebuild_captures()
logging.debug("Microscope successfully attached!")

# Create flask app
logging.info("Creating app")
app, labthing = create_app(
    __name__,
    prefix="/api/v2",
    title=f"OpenFlexure Microscope {api_microscope.name}",
    description="Test LabThing-based API for OpenFlexure Microscope",
    types=["org.openflexure.microscope"],
    version=pkg_resources.get_distribution("openflexure-microscope-server").version,
    flask_kwargs={"static_url_path": "", "static_folder": "static/dist"},
)

# Enable CORS for some routes outside of LabThings
cors: CORS = CORS(app)

# Use custom JSON encoder
labthing.json_encoder = JSONEncoder
app.json_encoder = JSONEncoder

# Add the microscope object to LabThings so extensions can access it
labthing.add_component(api_microscope, "org.openflexure.microscope")

# Attach extensions
# New-style extensions are explicitly enabled in the configuration file
extension_entry_points = extensions.find.entry_points_from_list(
    api_microscope.configuration["extensions_enabled"]
)
for entrypoint in extension_entry_points:
    extension_class = entrypoint.load()
    labthing.register_extension(extension_class())
# This loads old-style extensions and is deprecated
if os.path.isfile(OPENFLEXURE_EXTENSIONS_PATH):
    for extension in find_extensions(OPENFLEXURE_EXTENSIONS_PATH):
        logging.warning(
            f"Using an old-style extension {extension.__name__}.  "
            "Support for this will be removed in the future."
        )
        labthing.register_extension(extension)

# Add all the built-in (i.e. not extension) views to the labthing
# This defines the core API.
views.add_views_to_labthing(labthing)

# Serve the built-in web app at the root of the webserver
@app.route("/")
def openflexure_ev():
    return app.send_static_file("index.html")


@app.route("/routes")
@cross_origin()
def routes():
    """
    List of all connected API routes
    """
    return list_routes(app)


@app.route("/api/v1/", defaults={"path": ""})
@app.route("/api/v1/<path:path>")
def api_v1_catch_all(path):  # pylint: disable=W0613
    abort(410, "API v1 is no longer in use. Please upgrade your client.")


openapi.add_spec_extras(labthing.spec)


# Automatically clean up microscope at exit
def cleanup():
    logging.debug("App teardown started...")
    logging.debug("Settling...")
    time.sleep(0.5)

    # Save config
    logging.debug("Saving config for teardown...")
    api_microscope.save_settings()

    logging.debug("Settling...")
    time.sleep(0.5)

    # Close down the microscope
    logging.debug("Closing devices...")
    api_microscope.close()

    logging.debug("Settling...")
    time.sleep(0.5)

    logging.debug("App teardown complete.")


atexit.register(cleanup)


def ofm_serve():
    # Start a debug server
    from labthings import Server

    logging.info("Starting OpenFlexure Microscope Server...")
    server: Server = Server(app)
    server.run(host="0.0.0.0", port=5000, debug=log_level==logging.DEBUG, zeroconf=True)


def generate_openapi():
    """Generate an OpenAPI description and save as a file"""
    openapi.generate_openapi_from_labthing(labthing)

# Start the app if the module is run directly
if __name__ == "__main__":
    ofm_serve()
