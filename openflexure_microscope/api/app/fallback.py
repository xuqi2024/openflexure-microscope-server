#!/usr/bin/env python
import contextlib
import logging
import traceback
from typing import List, Tuple

import pkg_resources
from flask import Flask, abort, render_template_string
from flask_cors import CORS
from labthings import LabThing, create_app

# `logging_configuration` performs log file setup as an import side-effect
from openflexure_microscope.api.logging_configuration import log_level
from openflexure_microscope.json import JSONEncoder
from openflexure_microscope.config import user_configuration
from openflexure_microscope.paths import (
    OPENFLEXURE_EXTENSIONS_PATH,
    OPENFLEXURE_VAR_PATH,
)
from openflexure_microscope.utilities import ConfigurableComponentFailedToLoad


FALLBACK_HTML_PAGE = """
<html>
    <body>
        <h1>Configuration error</h1>
        <p>
            The server could not start, most likely because of an error in config.json.  In the future, this page should tell you what is wrong, but for now please log in using SSH and run <pre>ofm log</pre> to see the log.
        </p>
    </body>
</html>
"""


def create_fallback_app_and_labthing(e: ConfigurableComponentFailedToLoad) -> Tuple[Flask, LabThing]:
    """Create a flask app and labthing"""
    # Create flask app
    logging.info("Creating fallback app")
    app, labthing = create_app(
        __name__,
        prefix="/api/v2",
        title=f"OpenFlexure Microscope Configurator",
        description="Configuration error server for the OpenFlexure Microscope",
        types=["org.openflexure.microscope"],
        version=pkg_resources.get_distribution("openflexure-microscope-server").version,
        flask_kwargs={"static_url_path": "", "static_folder": "static/dist"},
    )

    # Enable CORS for some routes outside of LabThings
    cors: CORS = CORS(app)

    # Use custom JSON encoder
    labthing.json_encoder = JSONEncoder
    app.json_encoder = JSONEncoder

    config = user_configuration.load()
    
    # Serve the built-in web app at the root of the webserver
    @app.route("/")
    def openflexure_ev():
        return render_template_string(FALLBACK_HTML_PAGE)

    @app.route("/component_errors.json")
    def error_as_json():
        sanitised_errors = {}
        for k, v in e.loaded_components_and_errors.items():
            sanitised_errors[k] = {
                k: v.get(k, None) for k in ["loaded", "traceback"]
            }
        return sanitised_errors

    @app.route("/api/v1/", defaults={"path": ""})
    @app.route("/api/<path:path>")
    def api_catch_all(path):  # pylint: disable=W0613
        abort(
            500,
            "The microscope server could not start due to plugins or extensions failing to load."
            "  You most likely need to reset the configuration file.  "
            "See /errors.json or the HTML page at / for details.",
        )

    return app, labthing

# The code below is helpful to debug the fallback server.  However,
# it's worth noting that we will already have imported __init__, and so
# we'll already have created either a real app or a fallback app.
# This will most likely have implications for device acquisition, etc.

def fallback_serve():
    # Start a debug server
    from labthings import Server

    logging.info("Starting OpenFlexure Microscope Fallback Server manually...")
    app, labthing = create_fallback_app_and_labthing()
    server: Server = Server(app)
    server.run(
        host="0.0.0.0", port=5000, debug=log_level == logging.DEBUG, zeroconf=True
    )


# Start the app if the module is run directly
if __name__ == "__main__":
    fallback_serve()
