import logging
from contextlib import contextmanager
from typing import Iterator, Tuple

import labthings.fields as fields
from flask import abort
from labthings import find_component
from labthings.extensions import BaseExtension
from labthings.views import ActionView
from picamerax import PiCamera

from openflexure_microscope.camera.base import BaseCamera
from openflexure_microscope.microscope import Microscope

from .recalibrate_utils import (
    adjust_shutter_and_gain_from_raw,
    adjust_white_balance_from_raw,
    flat_lens_shading_table,
    get_channel_percentiles,
    lst_from_camera,
)


@contextmanager
def pause_stream(scamera: BaseCamera):
    """This context manager locks a streaming camera, and pauses the stream.

    The stream is re-enabled, with the original resolution, once the with
    block has finished.
    """
    with scamera.lock:
        assert (
            not scamera.record_active
        ), "We can't pause the camera's video stream while a recording is in progress."
        streaming = scamera.stream_active
        old_resolution = scamera.stream_resolution
        if streaming:
            logging.info("Stopping stream in pause_stream context manager")
            scamera.stop_stream()
        try:
            yield scamera
        finally:
            scamera.stream_resolution = old_resolution
            if streaming:
                logging.info("Restarting stream in pause_stream context manager")
                scamera.start_stream()


class LSTExtension(BaseExtension):
    def __init__(self) -> None:
        super().__init__(
            "org.openflexure.calibration.picamera",
            version="2.0.0-beta.1",
            description="Routines to perform flat-field correction on the camera.",
        )

        self.add_view(RecalibrateView, "/recalibrate", endpoint="recalibrate")
        self.add_view(
            FlattenLSTView,
            "/flatten_lens_shading_table",
            endpoint="flatten_lens_shading_table",
        )
        self.add_view(
            DeleteLSTView,
            "/delete_lens_shading_table",
            endpoint="delete_lens_shading_table",
        )
        self.add_view(
            GetRawChannelPercentilesView,
            "/get_raw_channel_percentiles",
            endpoint="get_raw_channel_percentiles",
        )
        self.add_view(
            AutoExposureFromRawView,
            "/auto_exposure_from_raw",
            endpoint="auto_exposure_from_raw",
        )
        self.add_view(
            AutoWhiteBalanceFromRawView,
            "/auto_white_balance_from_raw",
            endpoint="auto_white_balance_from_raw",
        )
        self.add_view(
            AutoLensShadingTableView,
            "/auto_lens_shading_table",
            endpoint="auto_lens_shading_table",
        )


@contextmanager
def find_picamera() -> Iterator[Tuple[PiCamera, BaseCamera, Microscope]]:
    """Locate the microscope and raise a sensible error if it's missing."""
    microscope = find_component("org.openflexure.microscope")

    if not microscope:
        abort(
            503, "No microscope connected. Unable to use camera calibration functions."
        )

    scamera = microscope.camera

    if not hasattr(scamera, "picamera"):
        abort(503, "The PiCamera calibration plugin requires a Raspberry Pi camera.")

    with scamera.lock:
        yield scamera.picamera, scamera, microscope


class RecalibrateView(ActionView):
    def post(self):
        """Reset the camera's settings.

        This generates new gains, exposure time, and lens shading
        table such that the background is as uniform as possible
        with a gray level of 230.  It takes a little while to run.

        This consists of three steps:

        * Reset gain and exposure time, then increase them until
          we have a suitably bright image
        * Set the auto white balance based on a raw image
        * Set the lens shading table based on a raw image

        Each of these steps has its own endpoint if you want to
        perform them separately.
        """
        with find_picamera() as (picamera, scamera, microscope):
            logging.info("Starting microscope recalibration...")
            adjust_shutter_and_gain_from_raw(picamera)
            adjust_white_balance_from_raw(picamera)
            lst = lst_from_camera(picamera)
            with pause_stream(scamera):
                picamera.lens_shading_table = lst
            microscope.save_settings()


class AutoLensShadingTableView(ActionView):
    def post(self):
        """Perform flat-field correction

        This routine acquires a new image (which should be an
        empty field of view, i.e. a perfect microscope would
        record a uniform white image), and then uses it to set
        the "lens shading table" such that future images will
        be corrected for vignetting.
        """
        with find_picamera() as (picamera, scamera, microscope):
            logging.info("Generating lens shading table")
            lst = lst_from_camera(picamera)
            with pause_stream(scamera):
                picamera.lens_shading_table = lst
            microscope.save_settings()


class FlattenLSTView(ActionView):
    def post(self):
        with find_picamera() as (picamera, scamera, microscope):
            with pause_stream(scamera):
                flat_lst = flat_lens_shading_table(picamera)
                picamera.lens_shading_table = flat_lst
            microscope.save_settings()


class DeleteLSTView(ActionView):
    def post(self):
        with find_picamera() as (picamera, scamera, microscope):
            with pause_stream(scamera):
                picamera.lens_shading_table = None
            microscope.save_settings()


percentile_field = fields.Float(
    load_default=99.9,
    metadata={
        "example": 99.9,
        "description": (
            "A float between 0 and 100 setting the centile to use "
            "to measure the white point of the image.  A value "
            "of 99.9 allows 0.1% of the pixels to be erroneously "
            "bright - this helps stability in low light."
        ),
    },
)


class AutoExposureFromRawView(ActionView):
    args = {
        "target_white_level": fields.Int(
            load_default=700,
            metadata={
                "example": 700,
                "description": (
                    "The pixel value (10-bit format) that we aim for when adjusting shutter/gain."
                ),
            },
        ),
        "max_iterations": fields.Int(
            load_default=20,
            metadata={
                "description": (
                    "The number of adjustments to the camera's settings to make before giving up."
                )
            },
        ),
        "tolerance": fields.Float(
            load_default=0.05,
            metadata={
                "example": 0.05,
                "description": (
                    "We stop adjusting when we get within this fraction of the target "
                    "value.  It is a number between 0 and 1, usually 0.01--0.1."
                ),
            },
        ),
        "percentile": percentile_field,
    }

    def post(self, args):
        with find_picamera() as (picamera, _, _):
            adjust_shutter_and_gain_from_raw(picamera, **args)


class AutoWhiteBalanceFromRawView(ActionView):
    args = {"percentile": percentile_field}

    def post(self, args):
        with find_picamera() as (picamera, _, _):
            adjust_white_balance_from_raw(picamera, **args)


class GetRawChannelPercentilesView(ActionView):
    args = {
        "percentile": fields.Float(
            metadata={
                "description": "A float between 0 and 100 setting the centile to calculate",
                "example": 99.9,
            }
        )
    }
    schema = fields.List(fields.Integer)

    def post(self, args):
        with find_picamera() as (picamera, _, _):
            return get_channel_percentiles(picamera, args["percentile"])
