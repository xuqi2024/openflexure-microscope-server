from __future__ import annotations
import logging
from fastapi import Response
from labthings_fastapi.thing_server import ThingServer
from labthings_sangaboard import SangaboardThing
from labthings_picamera2.thing import StreamingPiCamera2
from socket import gethostname

from .things.autofocus import AutofocusThing
from .things.camera_stage_mapping import CameraStageMapper
from .things.system_control import SystemControlThing
from .things.settings_manager import SettingsManager
from .things.auto_recentre_stage import RecentringThing, RangeofMotionThing
from .things.smart_scan import SmartScanThing, BackgroundDetectThing
from .things.micat import MicatThing
from .things.stitching import Stitcher
from .things.test import APITestThing
from .serve_static_files import add_static_files
from .logging import configure_logging, retrieve_log

configure_logging()

thing_server = ThingServer()
thing_server.add_thing(StreamingPiCamera2(), "/camera/")
thing_server.add_thing(SangaboardThing(), "/stage/")
thing_server.add_thing(RecentringThing(), "/auto_recentre_stage/")
thing_server.add_thing(RangeofMotionThing(), "/range_of_motion/")
thing_server.add_thing(AutofocusThing(), "/autofocus/")
thing_server.add_thing(CameraStageMapper(), "/camera_stage_mapping/")
thing_server.add_thing(SystemControlThing(), "/system_control/")
thing_server.add_thing(SettingsManager(), "/settings/")
thing_server.add_thing(SmartScanThing("application/openflexure-stitching/.venv/bin/openflexure-stitch"), "/smart_scan/")
thing_server.add_thing(BackgroundDetectThing(), "/background_detect/")
thing_server.add_thing(MicatThing(), "/micat/")
thing_server.add_thing(APITestThing(), "/api_test/")
try:
    add_static_files(thing_server.app)
except RuntimeError:
    print("Failed to add static files - you will have to do without them!")

# Add an endpoint to get the log
thing_server.app.get("/log/")(retrieve_log)


app = thing_server.app

# TODO: update openflexure connect to make this unnecessary!!
# The endpoints below fool OpenFlexure Connect into thinking we are a
# v2 microscope, so we show up correctly.
# This is necessary until Connect is rebuilt.
@app.get("/routes")
def routes_stub() -> dict[str, dict]:
    """A stub list of routes, used by OF Connect to identify the microscope"""
    fake_routes = [
        "/api/v2/",
        "/api/v2/streams/snapshot",
        "/api/v2/instrument/settings/name"
    ]
    return {url: {"url": url, "methods": ["GET"]} for url in fake_routes}

class JPEGResponse(Response):
    media_type = "image/jpeg"

@app.get("/api/v2/streams/snapshot")
@app.head("/api/v2/streams/snapshot")
async def thumbnail() -> JPEGResponse:
    """A low-resolution snapshot, for compatibility with OF connect"""
    blob = await thing_server.things["/camera/"].lores_mjpeg_stream.grab_frame()
    return JPEGResponse(blob)

@app.get("/api/v2/instrument/settings/name")
def get_hostname() -> str:
    """Get the hostname of the device, for compatibility with OF connect"""
    return gethostname()