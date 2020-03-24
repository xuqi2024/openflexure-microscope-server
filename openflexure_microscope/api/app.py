#!/usr/bin/env python

import time
import atexit
import logging, logging.handlers
import os
import pkg_resources

from flask import Flask, jsonify, send_file

from datetime import datetime

from flask_cors import CORS, cross_origin

from openflexure_microscope.api.utilities import list_routes, init_default_extensions

from openflexure_microscope.config import JSONEncoder
from openflexure_microscope.paths import (
    OPENFLEXURE_VAR_PATH,
    OPENFLEXURE_EXTENSIONS_PATH,
    settings_file_path,
    logs_file_path,
)

from labthings.server.quick import create_app
from labthings.server.extensions import find_extensions

from openflexure_microscope.api.microscope import default_microscope as api_microscope

from openflexure_microscope.api.v2 import views

# Handle logging
DEFAULT_LOGFILE = logs_file_path("openflexure_microscope.log")

logger = logging.getLogger()

error_formatter = logging.Formatter(
    "[%(asctime)s] [%(threadName)s] [%(levelname)s] %(message)s"
)

rotating_logfile = logging.handlers.RotatingFileHandler(
    DEFAULT_LOGFILE, maxBytes=1_000_000, backupCount=7
)

error_handlers = [rotating_logfile, logging.StreamHandler()]

for handler in error_handlers:
    handler.setFormatter(error_formatter)
    logger.addHandler(handler)

logger.setLevel(logging.INFO)


# Log server paths being used
logging.info(f"Running with data path {OPENFLEXURE_VAR_PATH}")

# Create flask app
app, labthing = create_app(
    __name__,
    prefix="/api/v2",
    title=f"OpenFlexure Microscope {api_microscope.name}",
    description="Test LabThing-based API for OpenFlexure Microscope",
    version=pkg_resources.get_distribution("openflexure_microscope").version,
    flask_kwargs={"static_url_path": ""},
)

# Enable CORS for some routes outside of LabThings
cors = CORS(app)

# Use custom JSON encoder
app.json_encoder = JSONEncoder

# Attach lab devices
labthing.add_component(api_microscope, "org.openflexure.microscope")

# Attach extensions
if not os.path.isfile(OPENFLEXURE_EXTENSIONS_PATH):
    init_default_extensions(OPENFLEXURE_EXTENSIONS_PATH)
for extension in find_extensions(OPENFLEXURE_EXTENSIONS_PATH):
    labthing.register_extension(extension)

# Attach captures resources
labthing.add_view(views.CaptureList, f"/captures")
labthing.add_root_link(views.CaptureList, "captures")

labthing.add_view(views.CaptureView, f"/captures/<id>")
labthing.add_view(views.CaptureDownload, f"/captures/<id>/download/<filename>")
labthing.add_view(views.CaptureTags, f"/captures/<id>/tags")
labthing.add_view(views.CaptureAnnotations, f"/captures/<id>/annotations")

# Attach settings and state resources
labthing.add_view(views.SettingsProperty, f"/instrument/settings")
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


# Attach streams resources
labthing.add_view(views.MjpegStream, f"/streams/mjpeg")
labthing.add_view(views.SnapshotStream, f"/streams/snapshot")

# Attach microscope action resources
labthing.add_view(views.actions.ActionsView, "/actions")
labthing.add_root_link(views.actions.ActionsView, "actions")
for name, action in views.enabled_root_actions().items():
    view_class = action["view_class"]
    rule = action["rule"]
    labthing.add_view(view_class, f"/actions{rule}")


@app.route("/")
def openflexure_ev():
    return app.send_static_file("index.html")


@app.route("/routes")
@cross_origin()
def routes():
    """
    List of all connected API routes
    """
    return jsonify(list_routes(app))


@app.route("/log")
def err_log():
    """
    Most recent 1mb of log output
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return send_file(
        DEFAULT_LOGFILE,
        as_attachment=True,
        attachment_filename="openflexure_microscope_{}.log".format(timestamp),
    )


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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port="5000", threaded=True, debug=True, use_reloader=False)
