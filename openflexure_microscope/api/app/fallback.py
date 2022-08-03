#!/usr/bin/env python
from dataclasses import asdict
import json
import logging
from typing import Tuple
import pkg_resources
from flask import Flask, abort, render_template_string, Response
from flask_cors import CORS
from labthings import LabThing, create_app

from openflexure_microscope.api.v2.views import LogFileView
from openflexure_microscope.json import JSONEncoder
from openflexure_microscope.config import MicroscopeConfig
from openflexure_microscope.extensions.load import ConfigurableComponentFailedToLoad

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
<a href="/details/">Detailed error information.</a>
        <h2>Current configuration</h2>
<pre>
{{config}}
</pre>
    </body>
</html>
"""

DETAILED_ERRORS_HTML_PAGE = """
<html>
<body>
<h1>Detailed error information</h1>
{% for result in results %}
<h2>{{result.type}}</h2>
{% if result.loaded %}
<b>SUCCESS</b>
{% else %}
<b>ERROR:</b> {{str(result.exception)}}
<pre>
{{result.traceback}}
</pre>
{% endif %}
{%endfor%}
</body>
</html>
"""


def create_fallback_app_and_labthing(
    config: MicroscopeConfig, e: ConfigurableComponentFailedToLoad
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

    labthing.add_view(LogFileView, "/log")

    # Serve the error page at the root of the webserver
    @app.route("/")
    def root_page():
        return render_template_string(
            FALLBACK_HTML_PAGE,
            error_summary=e.summary,
            config=json.dumps(asdict(config), indent=2),
        )

    @app.route("/details/")
    def details_page():
        return render_template_string(
            DETAILED_ERRORS_HTML_PAGE, results=e.results, str=str
        )

    @app.route("/component_errors.json")
    def error_as_json():
        return Response(json.dumps(e.json_safe_list), mimetype="application/json")

    @app.route("/config.json")
    def config_endpoint():
        return asdict(config)

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
