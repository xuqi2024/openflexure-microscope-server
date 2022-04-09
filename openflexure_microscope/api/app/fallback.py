#!/usr/bin/env python
import json
import logging
from typing import Tuple

import pkg_resources
from flask import Flask, abort, render_template_string
from flask_cors import CORS
from labthings import LabThing, create_app

# `logging_configuration` performs log file setup as an import side-effect
from openflexure_microscope.api.logging_configuration import log_level
from openflexure_microscope.api.v2.views import LogFileView
from openflexure_microscope.config import user_configuration
from openflexure_microscope.json import JSONEncoder
from openflexure_microscope.utilities import ConfigurableComponentFailedToLoad

FALLBACK_HTML_PAGE = """
<html>
    <body>
        <h1>Configuration error</h1>
        <p>
            The server could not start, most likely because of an error in config.json.  In the future, this page should tell you what is wrong, but for now please log in using SSH and run <pre>ofm log</pre> to see the log.
        </p>
        <h2>Summary of the errors</h2>
<pre>
{{error_summary}}
</pre>
        <h2>Current configuration</h2>
<pre>
{{config}}
</pre>
    </body>
</html>
"""


def create_fallback_app_and_labthing(
    e: ConfigurableComponentFailedToLoad
) -> Tuple[Flask, LabThing]:
    """Create a flask app and labthing"""
    # Create flask app
    logging.info("Creating fallback app")
    app, labthing = create_app(
        __name__,
        prefix="/api/v2",
        title="OpenFlexure Microscope",
        description="Configuration error server for the OpenFlexure Microscope",
        types=["org.openflexure.microscope"],
        version=pkg_resources.get_distribution("openflexure-microscope-server").version,
        flask_kwargs={"static_url_path": "", "static_folder": "static/dist"},
    )

    # Enable CORS for some routes outside of LabThings
    CORS(app)

    # Use custom JSON encoder
    labthing.json_encoder = JSONEncoder
    app.json_encoder = JSONEncoder

    config_dict = user_configuration.load()

    labthing.add_view(LogFileView, "/log")

    # Serve the built-in web app at the root of the webserver
    @app.route("/")
    def openflexure_ev():
        return render_template_string(
            FALLBACK_HTML_PAGE,
            error_summary=e.summary,
            config=json.dumps(config_dict, indent=2),
        )

    @app.route("/component_errors.json")
    def error_as_json():
        return e.json_safe_dict

    @app.route("/config.json")
    def config_endpoint():
        return config_dict

    @app.route("/api/v1/", defaults={"path": ""})
    @app.route("/api/<path:path>")
    def api_catch_all(path):  # pylint: disable=W0613
        abort(
            500,
            "The microscope server could not start due to plugins or extensions failing to load."
            "  You most likely need to reset the configuration file.  "
            "See /component_errors.json or the HTML page at / for details.",
        )

    return app, labthing


# NB it's not a good idea to try to run this with a __name__=="__main__"
# block, because of the side-effects of the `__init__` module in this
# folder, which will already create many of the objects in here.
