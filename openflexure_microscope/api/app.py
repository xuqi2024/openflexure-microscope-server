#!/usr/bin/env python

import time
import atexit
import logging
import sys
import os

from flask import Flask, jsonify, send_file

from serial import SerialException
from datetime import datetime

from flask_cors import CORS

from openflexure_microscope.api.exceptions import JSONExceptionHandler
from openflexure_microscope.api.utilities import list_routes

from openflexure_microscope import Microscope

from openflexure_microscope.camera.capture import build_captures_from_exif
from openflexure_microscope.config import USER_CONFIG_DIR
from openflexure_microscope.api.v1 import blueprints

# Import device modules
# NB this will eventually be handled by the RC file, so you can choose what device
# class should be attached.
try:
    from openflexure_microscope.camera.pi import PiCameraStreamer
except ImportError:
    logging.warning("Unable to import PiCameraStreamer")
from openflexure_microscope.camera.mock import MockStreamer

from openflexure_microscope.stage.sanga import SangaStage
from openflexure_microscope.stage.mock import MockStage


# Handle logging
is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")

DEFAULT_LOGFILE = os.path.join(USER_CONFIG_DIR, "openflexure_microscope.log")

if (__name__ == "__main__") or (not is_gunicorn):
    # If imported, but not by gunicorn
    print("Letting sys handle logs")
    logging.basicConfig(level=logging.DEBUG)
else:
    # Direct standard Python logging to file and console
    root = logging.getLogger()
    error_formatter = logging.Formatter(
        "[%(asctime)s] [%(threadName)s] [%(levelname)s] %(message)s"
    )

    rotating_logfile = logging.handlers.RotatingFileHandler(
        DEFAULT_LOGFILE, maxBytes=1000000, backupCount=7
    )

    error_handlers = [rotating_logfile, logging.StreamHandler()]

    for handler in error_handlers:
        handler.setFormatter(error_formatter)
        root.addHandler(handler)

    root.setLevel(logging.getLogger("gunicorn.error").level)

# Create a dummy microscope object, with no hardware attachments
api_microscope = Microscope()

# Initialise camera
logging.debug("Creating camera object...")
try:
    api_camera = PiCameraStreamer()
except Exception as e:
    logging.error(e)
    logging.warning("No valid camera hardware found. Falling back to mock camera!")
    api_camera = MockStreamer()

# Initialise stage
logging.debug("Creating stage object...")
try:
    api_stage = SangaStage()
except Exception as e:
    logging.error(e)
    logging.warning("No valid stage hardware found. Falling back to mock stage!")
    api_stage = MockStage()

# Attach devices to microscope
logging.debug("Attaching devices to microscope...")
api_microscope.attach(api_camera, api_stage)

# Restore loaded capture array to camera object
logging.debug("Restoring captures...")
api_microscope.camera.images = build_captures_from_exif(api_microscope.camera.paths["default"])

logging.debug("Microscope successfully attached!")

# Generate API URI based on version from filename
def uri(suffix, api_version, base=None):
    if not base:
        base = "/api/{}".format(api_version)
    return_uri = base + suffix
    logging.debug("Created app route: {}".format(return_uri))
    return return_uri


# Create flask app
app = Flask(__name__)
app.url_map.strict_slashes = False

CORS(app, resources=r"*")

# Make errors more API friendly
handler = JSONExceptionHandler(app)

# WEBAPP ROUTES

# Base routes
base_blueprint = blueprints.base.construct_blueprint(api_microscope)
app.register_blueprint(base_blueprint, url_prefix=uri("", "v1"))

# Stage routes
stage_blueprint = blueprints.stage.construct_blueprint(api_microscope)
app.register_blueprint(stage_blueprint, url_prefix=uri("/stage", "v1"))

# Camera routes
camera_blueprint = blueprints.camera.construct_blueprint(api_microscope)
app.register_blueprint(camera_blueprint, url_prefix=uri("/camera", "v1"))

# Plugin routes
plugin_blueprint = blueprints.plugins.construct_blueprint(api_microscope)
app.register_blueprint(plugin_blueprint, url_prefix=uri("/plugin", "v1"))

# Task routes
task_blueprint = blueprints.task.construct_blueprint(api_microscope)
app.register_blueprint(task_blueprint, url_prefix=uri("/task", "v1"))


@app.route("/routes")
def routes():
    """
    List of all connected API routes

    .. :quickref: System; Routes

    :>header Accept: application/json
    :>header Content-Type: application/json
    :status 200: stream active
    """
    return jsonify(list_routes(app))


@app.route("/log")
def err_log():
    """
    Most recent 1mb of log output

    .. :quickref: System; Log

    :>header Accept: application/json
    :>header Content-Type: application/json
    :status 200: stream active
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return send_file(
        DEFAULT_LOGFILE,
        as_attachment=True,
        attachment_filename="openflexure_microscope_{}.log".format(timestamp),
    )


# Automatically clean up microscope at exit
def cleanup():
    global api_microscope
    logging.debug("App teardown started...")
    logging.debug("Settling...")
    time.sleep(0.5)

    # Save config
    logging.debug("Saving config for teardown...")
    api_microscope.save_config(backup=True)

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
