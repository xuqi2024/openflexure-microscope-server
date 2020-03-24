from labthings.server.view import View
from labthings.server.find import find_component
from labthings.server.extensions import BaseExtension
from labthings.server.decorators import marshal_task, ThingAction

from labthings.core.tasks import taskify

from flask import abort

import logging

from .recalibrate_utils import recalibrate_camera, auto_expose_and_freeze_settings


def recalibrate(microscope):
    """Reset the camera's settings.

    This generates new gains, exposure time, and lens shading
    table such that the background is as uniform as possible
    with a gray level of 230.  It takes a little while to run.
    """
    scamera = microscope.camera
    with scamera.lock:
        assert not scamera.record_active, "Can't recalibrate while recording!"
        streaming = scamera.stream_active
        if streaming:
            logging.info("Stopping stream before recalibration")
            scamera.stop_stream_recording(resolution=(640, 480))
        old_resolution = scamera.camera.resolution
        try:
            scamera.camera.resolution = (640, 480)
            auto_expose_and_freeze_settings(scamera.camera)
            recalibrate_camera(scamera.camera)
        finally:
            scamera.camera.resolution = old_resolution
            microscope.save_settings()
            if streaming:
                logging.info("Restarting stream after recalibration")
                scamera.start_stream_recording()


@ThingAction
class RecalibrateView(View):
    @marshal_task
    def post(self):
        microscope = find_component("org.openflexure.microscope")

        if not microscope:
            abort(503, "No microscope connected. Unable to recalibrate.")

        logging.info("Starting microscope recalibration...")

        return taskify(recalibrate)(microscope)


lst_extension_v2 = BaseExtension(
    "org.openflexure.calibration.picamera", version="2.0.0-beta.1"
)

lst_extension_v2.add_method(
    recalibrate, "org.openflexure.calibration.picamera.recalibrate"
)

lst_extension_v2.add_view(RecalibrateView, "/recalibrate")
