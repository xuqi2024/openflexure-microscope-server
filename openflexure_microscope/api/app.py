#!/usr/bin/env python
import argparse
import atexit
import logging
import logging.handlers
import sys
import time

# Look for debug flag
if "-d" in sys.argv or "--debug" in sys.argv:
    debug_app = True
    log_level = logging.DEBUG
else:
    debug_app = False
    log_level = logging.INFO


# Set root logger level
root_log: logging.Logger = logging.getLogger()
root_log.setLevel(log_level)


import os
from datetime import datetime

import pkg_resources
from flask import abort, send_file
from flask_cors import CORS, cross_origin
from labthings import create_app
from labthings.extensions import find_extensions
from labthings.views import View

from openflexure_microscope.api.utilities import init_default_extensions, list_routes
from openflexure_microscope.api.v2 import views
from openflexure_microscope.json import JSONEncoder
from openflexure_microscope.microscope import Microscope
from openflexure_microscope.paths import (
    OPENFLEXURE_EXTENSIONS_PATH,
    OPENFLEXURE_VAR_PATH,
    logs_file_path,
)

from .openapi import add_spec_extras


# Custom RotatingFileHandler subclass
class CustomRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    A custom class for a rotating file log handler, with defaults we like.
    1MB per file, maximum of 5 historic files.
    Non-propagating logs (so we can separate access logs from error logs)
    Optional debugging level.
    """

    def __init__(self, filename: str, debug: bool = False) -> None:
        super().__init__(filename, maxBytes=1_000_000, backupCount=5)
        # Set formatter
        self.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(threadName)s] [%(levelname)s] %(message)s"
            )
        )
        # Never propagate
        self.propagate: bool = False
        # Conditionally enable debugging
        if debug:
            self.setLevel(logging.DEBUG)


# Log files
ROOT_LOGFILE: str = logs_file_path("openflexure_microscope.log")
ACCESS_LOGFILE: str = logs_file_path("openflexure_microscope.access.log")

# Our WSGI server uses Werkzeug, so use that for the access log
access_log: logging.Logger = logging.getLogger("werkzeug")
# Block the access logs from propagating up to the root logger
access_log.propagate = False

# Create error log file handler
fh: logging.Handler = CustomRotatingFileHandler(ROOT_LOGFILE, debug=debug_app)
# Create access log file handler
afh: logging.Handler = CustomRotatingFileHandler(ACCESS_LOGFILE, debug=debug_app)
# Add file handler to root logger
root_log.addHandler(fh)
access_log.addHandler(afh)

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
if not os.path.isfile(OPENFLEXURE_EXTENSIONS_PATH):
    init_default_extensions(OPENFLEXURE_EXTENSIONS_PATH)
for extension in find_extensions(OPENFLEXURE_EXTENSIONS_PATH):
    labthing.register_extension(extension)

# Attach captures resources
labthing.add_view(views.CaptureList, "/captures")
labthing.add_root_link(views.CaptureList, "captures")

labthing.add_view(views.CaptureView, "/captures/<id_>")
labthing.add_view(views.CaptureDownload, "/captures/<id_>/download/<filename>")
labthing.add_view(views.CaptureTags, "/captures/<id_>/tags")
labthing.add_view(views.CaptureAnnotations, "/captures/<id_>/annotations")

# Attach settings and state resources
labthing.add_view(views.SettingsProperty, "/instrument/settings")
labthing.add_root_link(views.SettingsProperty, "instrumentSettings")
labthing.add_view(views.NestedSettingsProperty, "/instrument/settings/<path:route>")
labthing.add_view(views.StateProperty, "/instrument/state")
labthing.add_view(views.NestedStateProperty, "/instrument/state/<path:route>")
labthing.add_root_link(views.StateProperty, "instrumentState")
labthing.add_view(views.ConfigurationProperty, "/instrument/configuration")
labthing.add_view(
    views.NestedConfigurationProperty, "/instrument/configuration/<path:route>"
)
labthing.add_root_link(views.ConfigurationProperty, "instrumentConfiguration")

# Attach stage resources
labthing.add_view(views.StageTypeProperty, "/instrument/stage/type")

# Attach camera resources
labthing.add_view(views.LSTImageProperty, "/instrument/camera/lst")

# Attach streams resources
labthing.add_view(views.MjpegStream, "/streams/mjpeg")
labthing.add_view(views.SnapshotStream, "/streams/snapshot")

# Attach microscope action resources
for name, action in views.enabled_root_actions().items():
    view_class = action["view_class"]
    rule = action["rule"]
    labthing.add_view(view_class, f"/actions{rule}")

# Add log file download view
class LogFileView(View):
    def get(self):
        """
        Most recent 1mb of log output
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return send_file(
            ROOT_LOGFILE,
            as_attachment=True,
            attachment_filename="openflexure_microscope_{}.log".format(timestamp),
        )


labthing.add_view(LogFileView, "/log")


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


add_spec_extras(labthing.spec)


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
    server.run(host="0.0.0.0", port=5000, debug=debug_app, zeroconf=True)


def generate_openapi():
    parser = argparse.ArgumentParser("Generate an OpenAPI specification document")
    parser.add_argument(
        "-o",
        dest="output",
        default="openapi.yaml",
        help=(
            "Specify the output filename.  If it ends in .json, we output JSON."
            "Use .yml or .yaml for YAML (which is the default"
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the API spec, returning an error code if it does not pass.",
    )
    args = parser.parse_args()
    if args.validate:
        import apispec.utils

        if apispec.utils.validate_spec(labthing.spec):
            print("OpenAPI specification validated OK.")
    fname = args.output
    if fname.endswith(".json"):
        import json

        with open(fname, "w", encoding="utf-8") as fd:
            json.dump(labthing.spec.to_dict(), fd)
    else:
        with open(fname, "w", encoding="utf-8") as fd:
            fd.write(labthing.spec.to_yaml())


# Start the app if the module is run directly
if __name__ == "__main__":
    ofm_serve()
