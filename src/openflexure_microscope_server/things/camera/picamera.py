"""Submodule for interacting with a Raspberry Pi camera using the Picamera2 library.

The Picamera2 library uses LibCamera as the underlying camera stack. This gives us
some control of the GPU pipeline for the image.

The API documentation for PiCamera2 is unfortunately not in a standard auto-generated
website. For documentation of the PiCamera2 API there is a PDF called
"The Picamera2 Library" available at:
https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf

For information on the algorithms used to tune/calibrate the Raspberry Pi Camera see
the guide called "Raspberry Pi Camera Algorithm and Tuning Guide"
Available at:
https://datasheets.raspberrypi.com/camera/raspberry-pi-camera-guide.pdf
"""

from __future__ import annotations
from typing import Annotated, Iterator, Literal, Mapping, Optional
from datetime import datetime
import json
import logging
import os
import tempfile
import time
from contextlib import contextmanager
from threading import RLock

from pydantic import BaseModel, BeforeValidator
import piexif
import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import Output

import labthings_fastapi as lt
from labthings_fastapi.exceptions import NotConnectedToServerError

from . import picamera_recalibrate_utils as recalibrate_utils
from . import BaseCamera, JPEGBlob, ArrayModel


class PicameraStreamOutput(Output):
    """An Output class that sends frames to a stream."""

    def __init__(self, stream: lt.outputs.MJPEGStream, portal: lt.deps.BlockingPortal):
        """Create an output that puts frames in an MJPEGStream.

        We need to pass the stream object, and also the blocking portal, because
        new frame notifications happen in the anyio event loop and frames are
        sent from a thread. The blocking portal enables thread-to-async
        communication.
        """
        Output.__init__(self)
        self.stream = stream
        self.portal = portal

    def outputframe(
        self, frame, _keyframe=True, _timestamp=None, _packet=None, _audio=False
    ):
        """Add a frame to the stream's ringbuffer."""
        self.stream.add_frame(frame, self.portal)


class SensorMode(BaseModel):
    """A Pydantic model holding all the information about a specific sensor mode.

    This data is as reported by the PiCamera2 module.
    """

    unpacked: str
    bit_depth: int
    size: tuple[int, int]
    fps: float
    crop_limits: tuple[int, int, int, int]
    exposure_limits: tuple[Optional[int], Optional[int], Optional[int]]
    format: Annotated[str, BeforeValidator(repr)]


class SensorModeSelector(BaseModel):
    """A Pydantic model holding the two values needed to select a PiCamera Sensor mode.

    Theses values are the output size and the bit depth.

    This is a Pydantic model so that it can be saved to disk.
    """

    output_size: tuple[int, int]
    bit_depth: int


class LensShading(BaseModel):
    """A Pydantic model holding the lens shading tables.

    PiCamera needs three numpy arrays for lens shading correction. Each array is
    (12, 16) in size. The arrays are luminance, red-difference chroma (Cr), and
    blue-difference chroma (Cb).

    This is a Pydantic modell so that it can be saved to the disk.
    """

    luminance: list[list[float]]
    Cr: list[list[float]]
    Cb: list[list[float]]


class StreamingPiCamera2(BaseCamera):
    """A Thing that represents an OpenCV camera."""

    def __init__(self, camera_num: int = 0):
        self._setting_save_in_progress = False
        self.camera_num = camera_num
        self.camera_configs: dict[str, dict] = {}
        self._picamera_lock = None
        self._picamera = None
        logging.info("Starting & reconfiguring camera to populate sensor_modes.")
        with Picamera2(camera_num=self.camera_num) as cam:
            self.default_tuning = recalibrate_utils.load_default_tuning(cam)
        logging.info("Done reading sensor modes & default tuning.")
        # Set tuning to default tuning. This will be overwritten when the Thing is
        # connects to the server if tuning is saved to disk.
        try:
            self.tuning = self.default_tuning
        except NotConnectedToServerError:
            # This will throw an error after setting as we are not connected to
            # a server. But we know this, so we ignore the error.
            pass

    stream_resolution = lt.ThingProperty(
        tuple[int, int],
        initial_value=(820, 616),
    )
    """Resolution to use for the MJPEG stream."""

    mjpeg_bitrate = lt.ThingProperty(
        Optional[int],
        initial_value=100000000,
    )
    """Bitrate for MJPEG stream (None for default)."""

    stream_active = lt.ThingProperty(
        bool,
        initial_value=False,
        observable=True,
        readonly=True,
    )
    """Whether the MJPEG stream is active."""

    def save_settings(self):
        """Override save_settings to ensure that camera properties don't recurse.

        This method is run by any Thing when a ThingSetting is saved. However, the
        method reads the thing_setting. As reading the thing setting talks to the
        camera and calls save_settings if the value is not as expected, this could
        cause recursion. Aslo this means that saving one setting causes all others
        to be read each time.
        """
        try:
            self._setting_save_in_progress = True
            super().save_settings()
        finally:
            self._setting_save_in_progress = False

    ## Persistent controls! These are settings

    _analogue_gain: float = 1.0

    @lt.thing_setting
    def analogue_gain(self) -> float:
        """The Analogue gain applied by the camera sensor."""
        if not self._setting_save_in_progress and self.streaming:
            with self._streaming_picamera() as cam:
                cam_value = cam.capture_metadata()["AnalogueGain"]
            if cam_value != self._analogue_gain:
                self._analogue_gain = cam_value
                self.save_settings()
        return self._analogue_gain

    @analogue_gain.setter
    def analogue_gain(self, value: float):
        self._analogue_gain = value
        if self.streaming:
            with self._streaming_picamera() as cam:
                cam.set_controls({"AnalogueGain": value})

    _colour_gains: tuple[float, float] = (1.0, 1.0)

    @lt.thing_setting
    def colour_gains(self) -> tuple[float, float]:
        """The red and blue colour gains, must be betwen 0.0 and 32.0."""
        if not self._setting_save_in_progress and self.streaming:
            with self._streaming_picamera() as cam:
                cam_value = cam.capture_metadata()["ColourGains"]
            if cam_value != self._colour_gains:
                self._colour_gains = cam_value
                self.save_settings()
        return self._colour_gains

    @colour_gains.setter
    def colour_gains(self, value: tuple[float, float]):
        self._colour_gains = value
        if self.streaming:
            with self._streaming_picamera() as cam:
                cam.set_controls({"ColourGains": value})

    _exposure_time: int = 0

    @lt.thing_setting
    def exposure_time(self) -> int:
        """The camera exposure time in microseconds.

        When setting this property the camera will adjust the set value
        to the nearest allowed value that is lower than the current setting.
        """
        if not self._setting_save_in_progress and self.streaming:
            with self._streaming_picamera() as cam:
                cam_value = cam.capture_metadata()["ExposureTime"]
            if cam_value != self._exposure_time:
                self._exposure_time = cam_value
                self.save_settings()
        return self._exposure_time

    @exposure_time.setter
    def exposure_time(self, value: int):
        _exposure_time = value
        if self.streaming:
            with self._streaming_picamera() as cam:
                # Note: This set a value 1 higher than requested as picamera2 always
                # sets a lower value than requested, even if the requested is allowed
                cam.set_controls({"ExposureTime": value + 1})

    def _get_persistent_controls(self) -> dict:
        discard_frames: int = 1
        if self.streaming:
            with self._streaming_picamera() as cam:
                # Discard frames, so data is fresh
                for i in range(discard_frames):
                    cam.capture_metadata()
        return {
            "AeEnable": False,
            "AnalogueGain": self.analogue_gain,
            "AwbEnable": False,
            "Brightness": 0,
            "ColourGains": self.colour_gains,
            "Contrast": 1,
            "ExposureTime": self.exposure_time,
            "Saturation": 1,
            "Sharpness": 1,
        }

    _sensor_modes = None

    @lt.thing_property
    def sensor_modes(self) -> list[SensorMode]:
        """All the available modes the current sensor supports."""
        if not self._sensor_modes:
            with self._streaming_picamera() as cam:
                self._sensor_modes = cam.sensor_modes
        return self._sensor_modes

    _sensor_mode: Optional[dict] = None

    @lt.thing_property
    def sensor_mode(self) -> Optional[SensorModeSelector]:
        """The intended sensor mode of the camera."""
        if self._sensor_mode is None:
            return None
        return SensorModeSelector(**self._sensor_mode)

    @sensor_mode.setter
    def sensor_mode(self, new_mode: Optional[SensorModeSelector | dict]):
        """Change the sensor mode used."""
        if new_mode is None:
            self._sensor_mode = None
        elif isinstance(new_mode, SensorModeSelector):
            self._sensor_mode = new_mode.model_dump()
        elif isinstance(new_mode, dict):
            self._sensor_mode = new_mode

        # By pausing the stream on when accessing, streaming_picamera
        # self._sensor_mode will be read and set when the stream restarts
        # after the context manager closes.
        with self._streaming_picamera(pause_stream=True):
            pass

    @lt.thing_property
    def sensor_resolution(self) -> Optional[tuple[int, int]]:
        """The native resolution of the camera's sensor."""
        with self._streaming_picamera() as cam:
            return cam.sensor_resolution

    tuning = lt.ThingSetting(Optional[dict], None, readonly=True)
    """The Raspberry PiCamera Tuning File JSON."""

    def _initialise_picamera(self):
        """Acquire the picamera device and store it as ``self._picamera``.

        This duplicates logic in ``Picamera2.__init__`` to provide a tuning file that
        will be read when the camera system initialises.
        """
        if self._picamera_lock is not None:
            # Don't close the camera if it's in use
            self._picamera_lock.acquire()
        with tempfile.NamedTemporaryFile("w") as tuning_file:
            json.dump(self.tuning, tuning_file)
            tuning_file.flush()  # but leave it open as closing it will delete it
            os.environ["LIBCAMERA_RPI_TUNING_FILE"] = tuning_file.name

            if self._picamera is not None:
                logging.info("Closing picamera object for reinitialisation")
                logging.info(
                    "Camera object already exists, closing for reinitialisation"
                )
                self._picamera.close()
                logging.info("Picamera closed, deleting picamera")
                del self._picamera
                recalibrate_utils.recreate_camera_manager()

            logging.info("Creating new Picamera2 object")
            # Specify tuning file otherwise it will be overwritten with None.
            self._picamera = Picamera2(
                camera_num=self.camera_num,
                tuning=self.tuning,
            )
        self._picamera_lock = RLock()

    def __enter__(self):
        self._initialise_picamera()
        # populate sensor modes by reading the property
        self.sensor_modes
        self.start_streaming()
        return self

    @property
    def streaming(self) -> bool:
        """True if the camera is streaming."""
        return self._picamera is not None and self._picamera.started

    @contextmanager
    def _streaming_picamera(self, pause_stream=False) -> Iterator[Picamera2]:
        """Lock access to picamera and return the underlying ``Picamera2`` instance.

        Optionally the stream can be paused to allow updating the camera settings.

        :param pause_stream: If False the ``Picamera2`` instance is simply yielded.
            If True:

                * Stop the MJPEG Stream
                * Yield the ``Picamera2`` instance for function calling the context manager to
                    make changes.
                * On closing of the context manager the stream will restart.
        """
        already_streaming = self.stream_active
        with self._picamera_lock:
            if pause_stream and already_streaming:
                self.stop_streaming(stop_web_stream=False)
            try:
                yield self._picamera
            finally:
                if pause_stream and already_streaming:
                    self.start_streaming()

    def __exit__(self, exc_type, exc_value, traceback):
        # Shut down the camera
        self.stop_streaming()
        with self._streaming_picamera() as cam:
            cam.close()
        del self._picamera

    @lt.thing_action
    def start_streaming(
        self, main_resolution: tuple[int, int] = (820, 616), buffer_count: int = 6
    ) -> None:
        """Start the MJPEG stream. This is where persistent controls are sent to camera.

        Sets the camera resolutions based on input parameters, and sets the low-res
        resolution to (320, 240). Note: (320, 240) is a standard from the Pi Camera
        manual.

        Create two streams:

        * ``lores_mjpeg_stream`` for autofocus at low-res resolution
        * ``mjpeg_stream`` for preview. This is the ``main_resolution`` if this is less
            than (1280, 960), or the low-res resolution if above. This allows for
            high resolution capture without streaming high resolution video.

        main_resolution: the resolution for the main configuration. Defaults to
        (820, 616), 1/4 sensor size.
        buffer_count: the number of frames to hold in the buffer. Higher uses more memory,
        lower may cause dropped frames. Value must be between 1 and 8, Defaults to 6.
        """
        controls = self._get_persistent_controls()
        # Buffer count can't be negative, zero, or too high.
        if buffer_count < 1 or buffer_count > 8:
            # 8 is slightly arbitrary. 6 is the PiCamera default for video
            # and the documentation only says that setting values higher gives
            # diminishing returns, and that the true maximum is hardware dependent
            raise ValueError(
                f"Can't set a buffer count of {buffer_count}. "
                "Buffer count must be an integer from 1-8"
            )
        with self._streaming_picamera() as picam:
            try:
                if picam.started:
                    picam.stop()
                    picam.stop_encoder()  # make sure there are no other encoders going
                stream_config = picam.create_video_configuration(
                    main={"size": main_resolution},
                    lores={"size": (320, 240), "format": "YUV420"},
                    sensor=self._sensor_mode,
                    controls=controls,
                )
                stream_config["buffer_count"] = buffer_count
                picam.configure(stream_config)
                logging.info("Starting picamera MJPEG stream...")
                stream_name = "lores" if main_resolution[0] > 1280 else "main"
                picam.start_recording(
                    MJPEGEncoder(self.mjpeg_bitrate),
                    PicameraStreamOutput(
                        self.mjpeg_stream,
                        lt.get_blocking_portal(self),
                    ),
                    name=stream_name,
                )
                picam.start_encoder(
                    MJPEGEncoder(100000000),
                    PicameraStreamOutput(
                        self.lores_mjpeg_stream,
                        lt.get_blocking_portal(self),
                    ),
                    name="lores",
                )
            except Exception as e:
                logging.exception("Error while starting preview: {e}")
                logging.exception(e)
            else:
                self.stream_active = True
                logging.debug(
                    "Started MJPEG stream at %s on port %s", self.stream_resolution, 1
                )

    @lt.thing_action
    def stop_streaming(self, stop_web_stream: bool = True) -> None:
        """Stop the MJPEG stream."""
        with self._streaming_picamera() as picam:
            try:
                picam.stop_recording()  # This should also stop the extra lores encoder
            except Exception as e:
                logging.info("Stopping recording failed")
                logging.exception(e)
            else:
                self.stream_active = False
                if stop_web_stream:
                    portal = lt.get_blocking_portal(self)
                    self.mjpeg_stream.stop(portal)
                    self.lores_mjpeg_stream.stop(portal)
                logging.info("Stopped MJPEG stream.")

            # Adding a sleep to prevent camera getting confused by rapid commands
            time.sleep(0.2)

    @lt.thing_action
    def capture_image(
        self,
        stream_name: Literal["main", "lores", "raw"] = "main",
        wait: Optional[float] = 0.9,
    ) -> None:
        """Acquire one image from the camera.

        Return it as a PIL Image

        stream_name: (Optional) The PiCamera2 stream to use, should be one of ["main", "lores", "raw"]. Default = "main"
        wait: (Optional, float) Set a timeout in seconds.
        A TimeoutError is raised if this time is exceeded during capture.
        Default = 0.9s, lower than the 1s timeout default in picamera yaml settings
        """
        with self._streaming_picamera() as cam:
            return cam.capture_image(stream_name, wait=wait)

    @lt.thing_action
    def capture_array(
        self,
        stream_name: Literal["main", "lores", "raw", "full"] = "main",
        wait: Optional[float] = 0.9,
    ) -> ArrayModel:
        """Acquire one image from the camera and return as an array.

        This function will produce a nested list containing an uncompressed RGB image.
        It's likely to be highly inefficient - raw and/or uncompressed captures using
        binary image formats will be added in due course.

        stream_name: (Optional) The PiCamera2 stream to use, should be one of ["main", "lores", "raw", "full"]. Default = "main"
        wait: (Optional, float) Set a timeout in seconds.
        A TimeoutError is raised if this time is exceeded during capture.
        Default = 0.9s, lower than the 1s timeout default in picamera yaml settings
        """
        # This was slower than capture_image for our use case, but directly returning
        # an image as an array is still a useful feature
        if stream_name == "full":
            with self._streaming_picamera(pause_stream=True) as picam2:
                capture_config = picam2.create_still_configuration()
                return picam2.switch_mode_and_capture_array(capture_config, wait=wait)
        with self._streaming_picamera() as cam:
            return cam.capture_array(stream_name, wait=wait)

    @lt.thing_property
    def camera_configuration(self) -> Mapping:
        """The "configuration" dictionary of the picamera2 object.

        The "configuration" sets the resolution and format of the camera's streams.
        Together with the "tuning" it determines how the sensor is configured and
        how the data is processed.

        Note that the configuration may be modified when taking still images, and
        this property refers to whatever configuration is currently in force -
        usually the one used for the preview stream.
        """
        with self._streaming_picamera() as cam:
            return cam.camera_configuration()

    @lt.thing_action
    def capture_jpeg(
        self,
        metadata_getter: lt.deps.GetThingStates,
        resolution: Literal["lores", "main", "full"] = "main",
        wait: Optional[float] = 0.9,
    ) -> JPEGBlob:
        """Acquire one image from the camera as a JPEG.

        The JPEG will be acquired using ``Picamera2.capture_file``. If the
        ``resolution`` parameter is ``main`` or ``lores``, it will be captured
        from the main preview stream, or the low-res preview stream,
        respectively. This means the camera won't be reconfigured, and
        the stream will not pause (though it may miss one frame).

        If ``full`` resolution is requested, we will briefly pause the
        MJPEG stream and reconfigure the camera to capture a full
        resolution image.

        wait: (Optional, float) Set a timeout in seconds.
        A TimeoutError is raised if this time is exceeded during capture.
        Default = 0.9s, lower than the 1s timeout default in picamera yaml settings

        Note that this always uses the image processing pipeline - to
        bypass this, you must use a raw capture.
        """
        fname = datetime.now().strftime("%Y-%m-%d-%H%M%S.jpeg")
        folder = tempfile.TemporaryDirectory()
        path = os.path.join(folder.name, fname)
        config = self.camera_configuration
        # Low-res and main streams are running already - so we don't need
        # to reconfigure for these
        if resolution in ("lores", "main") and config[resolution]:
            with self._streaming_picamera() as cam:
                cam.capture_file(path, name=resolution, format="jpeg", wait=wait)
        else:
            if resolution != "full":
                logging.warning(
                    f"There was no {resolution} stream, capturing full resolution"
                )
            with self._streaming_picamera(pause_stream=True) as cam:
                logging.info("Reconfiguring camera for full resolution capture")
                cam.configure(cam.create_still_configuration())
                cam.start()
                cam.options["quality"] = 95
                logging.info("capturing")
                cam.capture_file(path, name="main", format="jpeg", wait=wait)
                logging.info("done")
        # After the file is written, add metadata about the current Things
        exif_dict = piexif.load(path)
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = json.dumps(
            metadata_getter()
        ).encode("utf-8")
        piexif.insert(piexif.dump(exif_dict), path)
        return JPEGBlob.from_temporary_directory(folder, fname)

    @lt.thing_property
    def capture_metadata(self) -> dict:
        """Return the metadata from the camera."""
        with self._streaming_picamera() as cam:
            return cam.capture_metadata()

    @lt.thing_action
    def auto_expose_from_minimum(
        self,
        target_white_level: int = 700,
        percentile: float = 99.9,
    ):
        """Adjust exposure until a the target white level is reached.

        Starting from the minimum exposure, gradually increase exposure until
        the image reaches the specified white level.

        :param target_white_level: The target 10bit white level. 10-bit data has a
            theoretical maximum of 1023, but with black level correction the true
            maximum is about 950. Default is 700 as this is approximately 70%
            saturated.
        :param percentile: The percentile to use instead of maximum. Default 99.9. When
            calculating the brightest pixel, a percentile is used rather than the
            maximum in order to be robust to a small number of noisy/bright pixels.
        """
        with self._streaming_picamera(pause_stream=True) as cam:
            recalibrate_utils.adjust_shutter_and_gain_from_raw(
                cam,
                target_white_level=target_white_level,
                percentile=percentile,
            )

    @lt.thing_action
    def calibrate_white_balance(
        self,
        method: Literal["percentile", "centre"] = "centre",
        luminance_power: float = 1.0,
    ):
        """Correct the white balance of the image.

        This calibration requires a neutral image, such that the 99th centile
        of each colour channel should correspond to white. We calculate the
        centiles and use this to set the colour gains. This is done on the raw
        image with the lens shading correction applied, which should mean
        that the image is uniform, rather than weighted towards the centre.

        If ``method`` is ``"centre"``, we will correct the mean of the central 10%
        of the image.
        """
        with self._streaming_picamera(pause_stream=True) as cam:
            if self.lens_shading_is_static:
                lst: LensShading = self.lens_shading_tables
                recalibrate_utils.adjust_white_balance_from_raw(
                    cam,
                    percentile=99,
                    luminance=lst.luminance,
                    Cr=lst.Cr,
                    Cb=lst.Cb,
                    luminance_power=luminance_power,
                    method=method,
                )
            else:
                recalibrate_utils.adjust_white_balance_from_raw(
                    cam, percentile=99, method=method
                )

    @lt.thing_action
    def calibrate_lens_shading(self) -> None:
        """Take an image and use it for flat-field correction.

        This method requires an empty (i.e. bright) field of view. It will take
        a raw image and effectively divide every subsequent image by the current
        one. This uses the camera's "tuning" file to correct the preview and
        the processed images. It should not affect raw images.
        """
        with self._streaming_picamera(pause_stream=True) as cam:
            # Suppress lint warning that L, Cr, and Cb are not lowercase, as these are
            # the standard mathematical terms for:
            # luminance (L), red-difference chroma (Cr), and blue-difference chroma
            # (Cb).
            L, Cr, Cb = recalibrate_utils.lst_from_camera(cam)  # noqa: N806
            recalibrate_utils.set_static_lst(self.tuning, L, Cr, Cb)
            self._initialise_picamera()

    @lt.thing_property
    def colour_correction_matrix(
        self,
    ) -> tuple[float, float, float, float, float, float, float, float, float]:
        """The ``colour_correction_matrix`` from the tuning file.

        This is broken out into its own property for convenience and compatibility with
        the micromanager API

        Ir is a 9 value tuple used to specify the 3x3 matrix that the GPU pipeline uses
        to convert from the camera R,G,B vector to the standard R,G,B.

        See page Raspberry Pi Camera Algorithm and Tuning Guide, page 45.
        """
        return tuple(recalibrate_utils.get_static_ccm(self.tuning)[0]["ccm"])

    @colour_correction_matrix.setter  # type: ignore
    def colour_correction_matrix(self, value) -> None:
        recalibrate_utils.set_static_ccm(self.tuning, value)

        if self._picamera is not None:
            with self._streaming_picamera(pause_stream=True):
                self._initialise_picamera()

    @lt.thing_action
    def reset_ccm(self):
        """Overwrite the colour correction matrix in camera tuning with default values.

        These values are from the Raspberry Pi Camera Algorithm and Tuning Guide, page
        45.
        """
        # This is flattened 3x3 matrix. See `colour_correction_matrix`
        col_corr_matrix = [
            1.80439,
            -0.73699,
            -0.06739,
            -0.36073,
            1.83327,
            -0.47255,
            -0.08378,
            -0.56403,
            1.64781,
        ]
        self.colour_correction_matrix = col_corr_matrix

    @lt.thing_action
    def set_static_green_equalisation(self, offset: int = 65535) -> None:
        """Set the green equalisation to a static value.

        Green equalisation avoids the debayering algorithm becoming confused
        by the two green channels having different values, which is a problem
        when the chief ray angle isn't what the sensor was designed for, and
        that's the case in e.g. a microscope using camera module v2.

        A value of 0 here does nothing, a value of 65535 is maximum correction.
        """
        with self._streaming_picamera(pause_stream=True):
            recalibrate_utils.set_static_geq(self.tuning, offset)
            self._initialise_picamera()

    @lt.thing_action
    def full_auto_calibrate(self) -> None:
        """Perform a full auto-calibration.

        This function will call the other calibration actions in sequence:

        * ``flat_lens_shading`` to disable flat-field
        * ``auto_expose_from_minimum``
        * ``set_static_green_equalisation`` to set geq offset to max
        * ``calibrate_lens_shading``
        * ``calibrate_white_balance``
        """
        self.flat_lens_shading()
        self.auto_expose_from_minimum()
        self.set_static_green_equalisation()
        self.calibrate_lens_shading()
        self.calibrate_white_balance()

    @lt.thing_action
    def flat_lens_shading(self) -> None:
        """Disable flat-field correction.

        This method will set a completely flat lens shading table. It is not the
        same as the default behaviour, which is to use an adaptive lens shading
        table.

        This flat table is used to take an image wth no lens shading so that the
        correct lens shading table can be calibrated.
        """
        with self._streaming_picamera(pause_stream=True):
            # Generate and array of ones of the correct size for each channel
            flat_array = np.ones((12, 16))
            recalibrate_utils.set_static_lst(
                self.tuning, flat_array, flat_array, flat_array
            )
            self._initialise_picamera()

    @lt.thing_property
    def lens_shading_tables(self) -> Optional[LensShading]:
        """The current lens shading (i.e. flat-field correction).

        Return the current lens shading correction, as three 2D lists each with
        dimensions 16x12, if a static lens shading table is in use.

        Return None if:
        - adaptive control is enabled
        - multiple LSTs in use (for different colour temperatures),
        """
        if not self.lens_shading_is_static:
            return None

        # Note "alsc" is the Picamera2 term for "Automatic Lens Shading Correction"
        alsc = Picamera2.find_tuning_algo(self.tuning, "rpi.alsc")

        # Check there is exactly 1 correction table for red-difference chroma (Cr)
        # and blue-difference chroma (Cb)
        if len(alsc["calibrations_Cr"]) != 1 or len(alsc["calibrations_Cb"]) != 1:
            # If there is not exactly one table, then lens shading isn't static.
            return None

        def reshape_lst(lin: list[float]) -> list[list[float]]:
            """Reshape the 192 element list into a 2D 16x12 list."""
            w, h = 16, 12
            return [lin[w * i : w * (i + 1)] for i in range(h)]

        return LensShading(
            luminance=reshape_lst(alsc["luminance_lut"]),
            Cr=reshape_lst(alsc["calibrations_Cr"][0]["table"]),
            Cb=reshape_lst(alsc["calibrations_Cb"][0]["table"]),
        )

    @lens_shading_tables.setter
    def lens_shading_tables(self, lst: LensShading) -> None:
        """Set the lens shading tables."""
        with self._streaming_picamera(pause_stream=True):
            recalibrate_utils.set_static_lst(
                self.tuning,
                luminance=lst.luminance,
                cr=lst.Cr,
                cb=lst.Cb,
            )
            self._initialise_picamera()

    def correct_colour_gains_for_lens_shading(
        self, colour_gains: tuple[float, float]
    ) -> tuple[float, float]:
        """Correct white balance gains for the effect of lens shading.

        The white balance algorithm we use assumes the brightest pixels
        should be white, and that the only thing affecting the colour of
        said pixels is the ``colour_gains``.

        The lens shading correction is normalised such that the *minimum*
        gain in the ``Cr`` and ``Cb`` channels is 1. The white balance
        assumption above requires that the gain for the brightest pixels
        is 1. The solution might be that, when calibrating, we note which
        pixels are brightest (usually the centre) and explicitly use
        the LST values for there. However, for now I will assume that we
        need to normalise by the **maximum** of the ``Cr`` and ``Cb``
        channels, which is correct the majority of the time.
        """
        if not self.lens_shading_is_static:
            return colour_gains
        lst = self.lens_shading_tables
        # The Cr and Cb corrections are normalised to have a minimum of 1,
        # but the white balance algorithm normalises the brightest pixels
        # to be white, assuming the brightest pixels have equal gain from
        # the LST.
        gain_r, gain_b = colour_gains
        return (
            float(gain_r / np.max(lst.Cr)),
            float(gain_b / np.max(lst.Cb)),
        )

    @lt.thing_action
    def flat_lens_shading_chrominance(self) -> None:
        """Disable flat-field correction.

        This method will set the chrominance of the lens shading table to be
        flat, i.e. we'll correct vignetting of intensity, but not any change in
        colour across the image.
        """
        with self._streaming_picamera(pause_stream=True):
            alsc = Picamera2.find_tuning_algo(self.tuning, "rpi.alsc")
            luminance = alsc["luminance_lut"]
            flat = np.ones((12, 16))
            recalibrate_utils.set_static_lst(self.tuning, luminance, flat, flat)
            self._initialise_picamera()

    @lt.thing_action
    def reset_lens_shading(self) -> None:
        """Revert to default lens shading settings.

        This method will restore the default "adaptive" lens shading method used
        by the Raspberry Pi camera.
        """
        with self._streaming_picamera(pause_stream=True):
            recalibrate_utils.copy_alsc_section(self.default_tuning, self.tuning)
            self._initialise_picamera()

    @lt.thing_property
    def lens_shading_is_static(self) -> bool:
        """Whether the lens shading is static.

        This property is true if the lens shading correction has been set to use
        a static table (i.e. the number of automatic correction iterations is zero).
        The default LST is not static, but all the calibration controls will set it
        to be static (except "reset")
        """
        return recalibrate_utils.lst_is_static(self.tuning)
