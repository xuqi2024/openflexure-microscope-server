"""
This module contains the code that sets up the app.

It's split out so we can more easily switch to a fallback application if
needed, for example if the configuration means it can't start.

This module should not have import-time side-effects.
"""

#!/usr/bin/env python
import logging
import os
from typing import List, Tuple

import pkg_resources
from flask import Flask, abort
from flask_cors import CORS
from labthings import LabThing, create_app
from labthings.extensions import BaseExtension

from openflexure_microscope.api import openapi

# `logging_configuration` performs log file setup as an import side-effect
from openflexure_microscope.api.utilities import list_routes
from openflexure_microscope.api.v2 import views
from openflexure_microscope.captures import CaptureManager
from openflexure_microscope.extensions.load import MicroscopeComponents
from openflexure_microscope.json import JSONEncoder
from openflexure_microscope.microscope import Microscope
from openflexure_microscope.paths import OpenFlexurePaths
from openflexure_microscope.settings import OpenflexureSettingsFile


def create_app_and_labthing(
    components: MicroscopeComponents,
    paths: OpenFlexurePaths
) -> Tuple[Flask, LabThing]:
    """Create the labthing and flask application
    
    After successfully loading the hardware/extensions according
    to the configuration file, this function will set up the 
    application.
    """
    logging.info("Creating microscope")
    api_microscope = Microscope(
        components.camera, 
        components.stage,
        OpenflexureSettingsFile(os.path.join(paths.settings, "microscope_settings.json")),
        CaptureManager(os.path.join(paths.data, "micrographs")),
    )
    logging.info("Creating app")
    application, labthing = create_app(
        __name__,
        prefix="/api/v2",
        title=f"OpenFlexure Microscope {api_microscope.name}",
        description="Test LabThing-based API for OpenFlexure Microscope",
        types=["org.openflexure.microscope"],
        version=pkg_resources.get_distribution("openflexure-microscope-server").version,
        flask_kwargs={"static_url_path": "", "static_folder": "static/dist"},
    )

    # Enable CORS for all routes
    CORS(application)

    # Use custom JSON encoder (to handle numpy arrays better)
    labthing.json_encoder = JSONEncoder
    application.json_encoder = JSONEncoder

    # Add the microscope object to LabThings so extensions can access it
    labthing.add_component(api_microscope, "org.openflexure.microscope")

    # Attach extensions
    for extension in components.extensions:
        labthing.register_extension(extension)

    # Add all the built-in (i.e. not extension) views to the labthing
    # This defines the core API.
    views.add_views_to_labthing(labthing)

    # Serve the built-in web app at the root of the webserver
    @application.route("/")
    def openflexure_ev():
        return application.send_static_file("index.html")

    @application.route("/routes")
    def routes():
        """
        List of all connected API routes
        """
        return list_routes(application)

    @application.route("/api/v1/", defaults={"path": ""})
    @application.route("/api/v1/<path:path>")
    def api_v1_catch_all(path):  # pylint: disable=W0613
        abort(410, "API v1 is no longer in use. Please upgrade your client.")

    openapi.add_spec_extras(labthing.spec)

    return application, labthing
