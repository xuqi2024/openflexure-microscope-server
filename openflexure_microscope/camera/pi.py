# -*- coding: utf-8 -*-

"""
Raspberry Pi camera implementation of the PiCameraStreamer class.

**NOTES:**

Still port used for image capture.
Preview port reserved for onboard GPU preview.

Video port:

* Splitter port 0: Image capture (if `use_video_port == True`)
* Splitter port 1: Streaming frames
* Splitter port 2: Video capture
* Splitter port 3: [Currently unused]

PiCameraStreamer streams at video_resolution

Camera capture resolution set to stream_resolution in frames()

Video port uses that resolution for everything. If a different resolution
is specified for video capture, this is handled by the resizer.

Still capture (if use_video_port == False) uses pause_stream
to temporarily increase the capture resolution.
"""

from __future__ import division

import io
import time
import numpy as np
import os
import logging

# Pi camera
import picamera
import picamera.array

# Type hinting
from typing import Tuple

from .base import BaseCamera, CaptureObject

# Richard's fix gain
from .set_picamera_gain import set_analog_gain, set_digital_gain

from openflexure_microscope.paths import settings_file_path
from openflexure_microscope.utilities import (
    serialise_array_b64,
    ndarray_to_json,
    json_to_ndarray,
)


# MAIN CLASS
class PiCameraStreamer(BaseCamera):
    """Raspberry Pi camera implementation of PiCameraStreamer."""

    picamera_settings_keys = [
        "exposure_mode",
        "analog_gain",
        "digital_gain",
        "shutter_speed",
        "awb_gains",
        "awb_mode",
        "framerate",
        "saturation",
        "iso",
        "brightness",
        "contrast",
        "crop",
        "drc_strength",
        "exposure_compensation",
        "image_effect",
        "meter_mode",
        "sharpness",
        "annotate_text",
        "annotate_text_size",
        "zoom",
    ]

    def __init__(self):
        # Run BaseCamera init
        BaseCamera.__init__(self)
        # Attach to Pi camera
        self.camera = (
            picamera.PiCamera()
        )  #: :py:class:`picamera.PiCamera`: Picamera object

        # Store state of PiCameraStreamer
        self.preview_active = False

        # Reset variable states
        self.set_zoom(1.0)

        # Set default settings
        self.image_resolution = tuple(
            self.camera.MAX_RESOLUTION
        )  #: tuple: Resolution for image captures
        self.stream_resolution = (
            832,
            624,
        )  #: tuple: Resolution for stream and video captures
        self.numpy_resolution = (
            1312,
            976,
        )  #: tuple: Resolution for numpy array captures
        self.jpeg_quality = 75  #: int: JPEG quality

        # Set default lens shading table path
        self.picamera_lst_path = settings_file_path(
            "picamera_lst.npy"
        )  #: str: Path of .npy lens shading table file

        # Create an empty stream
        self.stream = io.BytesIO()

        # Start streaming
        self.start_worker()

    @property
    def configuration(self):
        """The current camera configuration."""
        return {"board": self.camera.revision}

    @property
    def state(self):
        """The current read-only camera state."""
        return {}

    def initialisation(self):
        """Run any initialisation code when the frame iterator starts."""
        pass

    def close(self):
        """Close the Raspberry Pi PiCameraStreamer."""
        # Run BaseCamera close method
        BaseCamera.close(self)
        # Detach Pi camera
        if self.camera:
            self.camera.close()

    # HANDLE SETTINGS
    def read_settings(self) -> dict:
        """
        Return config dictionary of the PiCameraStreamer.
        """

        # Get config items from the base class
        conf_dict = BaseCamera.read_settings(self)

        # Include device-specific config items
        conf_dict.update(
            {
                "stream_resolution": self.stream_resolution,
                "image_resolution": self.image_resolution,
                "numpy_resolution": self.numpy_resolution,
                "jpeg_quality": self.jpeg_quality,
                "picamera": {},
            }
        )

        # Include a subset of picamera properties. Excludes lens shading table
        for key in PiCameraStreamer.picamera_settings_keys:
            try:
                value = getattr(self.camera, key)
                logging.debug("Reading PiCamera().{}: {}".format(key, value))
                conf_dict["picamera"][key] = value
            except AttributeError:
                logging.debug("Unable to read PiCamera attribute {}".format(key))

        # Include a serialised lens shading table
        if (
            hasattr(self.camera, "lens_shading_table")
            and getattr(self.camera, "lens_shading_table") is not None
        ):
            conf_dict["picamera"]["lens_shading_table"] = ndarray_to_json(
                getattr(self.camera, "lens_shading_table")
            )

        return conf_dict

    def update_settings(self, config: dict):
        """
        Write a config dictionary to the PiCameraStreamer config.

        The passed dictionary may contain other parameters not relevant to
        camera config. Eg. Passing a general config file will work fine.

        Args:
            config (dict): Dictionary of config parameters.
        """

        paused_stream = False
        logging.debug("PiCameraStreamer: Applying config:")
        logging.debug(config)

        with self.lock:

            # Apply valid config params to Picamera object
            if not self.record_active:  # If not recording a video

                # Pause stream while changing settings
                if self.stream_active:  # If stream is active
                    logging.info("Pausing stream to update config.")
                    self.stop_stream_recording()  # Pause stream
                    paused_stream = True  # Remember to unpause stream when done

                # PiCamera parameters
                if "picamera" in config:  # If new settings are given
                    self.apply_picamera_settings(
                        config["picamera"], pause_for_effect=True
                    )

                    # Handle lens shading if camera supports it
                    if (
                        hasattr(self.camera, "lens_shading_table")
                        and "lens_shading_table" in config["picamera"]
                    ):
                        try:
                            self.camera.lens_shading_table = json_to_ndarray(
                                config["picamera"].get("lens_shading_table")
                            )
                        except KeyError as e:
                            logging.error(e)

                # PiCameraStreamer parameters
                for key, value in config.items():  # For each provided setting
                    if (key != "picamera") and hasattr(self, key):
                        setattr(self, key, value)

                # If stream was paused to update config, unpause
                if paused_stream:
                    logging.info("Resuming stream.")
                    self.start_stream_recording()

            else:
                raise Exception(
                    "Cannot update camera config while recording is active."
                )

    def apply_picamera_settings(
        self, settings_dict: dict, pause_for_effect: bool = True
    ):
        """

        Args:
            settings_dict (dict): Dictionary of properties to apply to the :py:class:`picamera.PiCamera`: object
            pause_for_effect (bool): Pause tactically to reduce risk of timing issues
        """
        # Set exposure mode
        if "exposure_mode" in settings_dict:
            logging.debug(
                "Applying exposure_mode: {}".format(settings_dict["exposure_mode"])
            )
            self.camera.exposure_mode = settings_dict["exposure_mode"]

        # Apply gains and let them settle
        if "analog_gain" in settings_dict:
            logging.debug(
                "Applying analog_gain: {}".format(settings_dict["analog_gain"])
            )
            set_analog_gain(self.camera, float(settings_dict["analog_gain"]))
        if "digital_gain" in settings_dict:
            logging.debug(
                "Applying digital_gain: {}".format(settings_dict["digital_gain"])
            )
            set_digital_gain(self.camera, float(settings_dict["digital_gain"]))

        # Apply shutter speed
        if "shutter_speed" in settings_dict:
            logging.debug(
                "Applying shutter_speed: {}".format(settings_dict["shutter_speed"])
            )
            self.camera.shutter_speed = int(settings_dict["shutter_speed"])

        time.sleep(0.2)  # Let gains settle

        # Handle AWB in a half-smart way
        if "awb_gains" in settings_dict:
            logging.debug("Applying awb_mode: off")
            self.camera.awb_mode = "off"
            logging.debug("Applying awb_gains: {}".format(settings_dict["awb_gains"]))
            self.camera.awb_gains = settings_dict["awb_gains"]
        elif "awb_mode" in settings_dict:
            logging.debug("Applying awb_mode: {}".format(settings_dict["awb_mode"]))
            self.camera.awb_mode = settings_dict["awb_mode"]

        # Handle some properties that can be quickly applied
        batched_keys = ["framerate", "saturation"]
        for key in batched_keys:
            if (key in settings_dict) and hasattr(self.camera, key):
                logging.debug("Applying {}: {}".format(key, settings_dict[key]))
                setattr(self.camera, key, settings_dict[key])

        # Final optional pause to settle
        if pause_for_effect:
            time.sleep(0.2)

    def set_zoom(self, zoom_value: float = 1.0) -> None:
        """
        Change the camera zoom, handling re-centering and scaling.
        """
        with self.lock:
            self.zoom_value = float(zoom_value)
            if self.zoom_value < 1:
                self.zoom_value = 1
            # Richard's code for zooming !
            fov = self.camera.zoom
            centre = np.array([fov[0] + fov[2] / 2.0, fov[1] + fov[3] / 2.0])
            size = 1.0 / self.zoom_value
            # If the new zoom value would be invalid, move the centre to
            # keep it within the camera's sensor (this is only relevant
            # when zooming out, if the FoV is not centred on (0.5, 0.5)
            for i in range(2):
                if np.abs(centre[i] - 0.5) + size / 2 > 0.5:
                    centre[i] = 0.5 + (1.0 - size) / 2 * np.sign(centre[i] - 0.5)
            logging.info("setting zoom, centre {}, size {}".format(centre, size))
            new_fov = (centre[0] - size / 2, centre[1] - size / 2, size, size)
            self.camera.zoom = new_fov

    # LAUNCH ACTIONS

    def start_preview(self, fullscreen=True, window=None):
        """Start the on board GPU camera preview."""
        logging.info("Starting the GPU preview")

        try:
            if not self.camera.preview:
                logging.debug("Starting preview")
                self.camera.start_preview(fullscreen=fullscreen, window=window)
            else:
                logging.debug("Resizing preview")
                if window:
                    self.camera.preview.window = window
                if fullscreen:
                    self.camera.preview.fullscreen = fullscreen
            self.preview_active = True
        except picamera.exc.PiCameraMMALError as e:
            logging.error(
                "Suppressed a MMALError in start_preview. Exception: {}".format(e)
            )
        except picamera.exc.PiCameraValueError as e:
            logging.error(
                "Suppressed a ValueError exception in start_preview. Exception: {}".format(
                    e
                )
            )

    def stop_preview(self):
        """Stop the on board GPU camera preview."""
        self.camera.stop_preview()
        self.preview_active = False

    def start_recording(self, output, fmt: str = "h264", quality: int = 15):
        """Start recording.

        Start a new video recording, writing to a output object.

        Args:
            output: String or file-like object to write capture data to
            fmt (str): Format of the capture.
            quality (int): Video recording quality.

        Returns:
            output_object (str/BytesIO): Target object.

        """
        with self.lock:
            # Start recording method only if a current recording is not running
            if not self.record_active:

                # Start the camera video recording on port 2
                logging.info("Recording to {}".format(output))

                self.camera.start_recording(
                    output,
                    format=fmt,
                    splitter_port=2,
                    resize=self.stream_resolution,
                    quality=quality,
                )

                # Update state
                self.record_active = True

                return output

            else:
                logging.warning(
                    "Cannot start a new recording\
                    until the current recording has stopped."
                )
                return None

    def stop_recording(self):
        """Stop the last started video recording on splitter port 2."""
        with self.lock:
            # Stop the camera video recording on port 2
            logging.info("Stopping recording")
            self.camera.stop_recording(splitter_port=2)
            logging.info("Recording stopped")

            # Update state
            self.record_active = False

    def stop_stream_recording(
        self, splitter_port: int = 1, resolution: Tuple[int, int] = None
    ) -> None:
        """
        Sets the camera resolution to the still-image resolution, and stops recording if the stream is active.

        Args:
            splitter_port (int): Splitter port to stop recording on
            resolution ((int, int)): Resolution to set the camera to, after stopping recording.
        """
        with self.lock:
            # If no resolution is specified, default to image_resolution
            if not resolution:
                resolution = self.image_resolution

            # Stop the camera video recording on port 1
            try:
                self.camera.stop_recording(splitter_port=splitter_port)
            except picamera.exc.PiCameraNotRecording:
                logging.info("Not recording on splitter_port {}".format(splitter_port))
            else:
                logging.info(
                    "Stopped MJPEG stream on port {1}. Switching to {0}.".format(
                        resolution, splitter_port
                    )
                )

            # Increase the resolution for taking an image
            time.sleep(
                0.2
            )  # Sprinkled a sleep to prevent camera getting confused by rapid commands
            self.camera.resolution = resolution

    def start_stream_recording(
        self, splitter_port: int = 1, resolution: Tuple[int, int] = None
    ) -> None:
        """
        Sets the camera resolution to the video/stream resolution, and starts recording if the stream should be active.

        Args:
            splitter_port (int): Splitter port to start recording on
            resolution ((int, int)): Resolution to set the camera to, before starting recording. 
                Defaults to `self.stream_resolution`.
        """
        with self.lock:
            # If stream object was destroyed
            if not hasattr(self, "stream"):
                self.stream = io.BytesIO()  # Create a stream object

            # If no explicit resolution is passed
            if not resolution:
                resolution = (
                    self.stream_resolution
                )  # Default to video recording resolution

            # Reduce the resolution for video streaming
            try:
                self.camera._check_recording_stopped()
            except picamera.exc.PiCameraRuntimeError:
                logging.info(
                    "Error while changing resolution: Recording already running."
                )
            else:
                self.camera.resolution = resolution

            # If the stream should be active
            if self.stream_active:
                try:
                    # Start recording on stream port
                    self.camera.start_recording(
                        self.stream,
                        format="mjpeg",
                        quality=self.jpeg_quality,
                        bitrate=-1,  # RWB: disable bitrate control
                        # (bitrate control makes JPEG size less good as a focus
                        # metric)
                        splitter_port=splitter_port,
                    )
                except picamera.exc.PiCameraAlreadyRecording:
                    logging.info(
                        "Error while starting preview: Recording already running."
                    )
                else:
                    logging.debug(
                        "Started MJPEG stream at {} on port {}".format(
                            resolution, splitter_port
                        )
                    )

    def capture(
        self,
        output,
        fmt: str = "jpeg",
        use_video_port: bool = False,
        resize: Tuple[int, int] = None,
        bayer: bool = True,
    ):
        """
        Capture a still image to a StreamObject.

        Defaults to JPEG format.
        Target object can be overridden for development purposes.

        Args:
            output: String or file-like object to write capture data to
            fmt (str): Format of the capture.
            use_video_port (bool): Capture from the video port used for streaming. Lower resolution, faster.
            resize ((int, int)): Resize the captured image.
            bayer (bool): Store raw bayer data in capture

        Returns:
            output_object (str/BytesIO): Target object.
        """

        if isinstance(output, CaptureObject):
            target = output.file
        else:
            target = output

        with self.lock:
            logging.info("Capturing to {}".format(output))

            # Set resolution and stop stream recording if necessary
            if not use_video_port:
                self.stop_stream_recording()

            self.camera.capture(
                target,
                format=fmt,
                quality=100,
                resize=resize,
                bayer=(not use_video_port) and bayer,
                use_video_port=use_video_port,
            )

            # Set resolution and start stream recording if necessary
            if not use_video_port:
                self.start_stream_recording()

            return target

    def yuv(
        self, use_video_port: bool = True, resize: Tuple[int, int] = None
    ) -> np.ndarray:
        """Capture an uncompressed still YUV image to a Numpy array.

        Args:
            use_video_port (bool): Capture from the video port used for streaming. Lower resolution, faster.
            resize ((int, int)): Resize the captured image.

        Returns:
            output_array (np.ndarray): Output array of capture
        """
        with self.lock:
            if use_video_port:
                resolution = self.stream_resolution
            else:
                resolution = self.numpy_resolution

            if resize:
                size = resize
            else:
                size = resolution

            if not use_video_port:
                self.stop_stream_recording(resolution=resolution)

            logging.debug("Creating PiYUVArray")
            with picamera.array.PiYUVArray(self.camera, size=size) as output:

                logging.info("Capturing to {}".format(output))

                self.camera.capture(
                    output, resize=size, format="yuv", use_video_port=use_video_port
                )

                if not use_video_port:
                    self.start_stream_recording()

                return output.array

    def array(
        self, use_video_port: bool = True, resize: Tuple[int, int] = None
    ) -> np.ndarray:
        """Capture an uncompressed still RGB image to a Numpy array.

        Args:
            use_video_port (bool): Capture from the video port used for streaming. Lower resolution, faster.
            resize ((int, int)): Resize the captured image.

        Returns:
            output_array (np.ndarray): Output array of capture
        """
        with self.lock:
            if use_video_port:
                resolution = self.stream_resolution
            else:
                resolution = self.numpy_resolution

            if resize:
                size = resize
            else:
                size = resolution

            # Always pause stream, to prevent resizer memory issues
            self.stop_stream_recording(resolution=resolution)

            logging.debug("Creating PiRGBArray")
            with picamera.array.PiRGBArray(self.camera, size=size) as output:

                logging.info("Capturing to {}".format(output))

                self.camera.capture(
                    output, resize=size, format="rgb", use_video_port=use_video_port
                )

                # Resume stream
                self.start_stream_recording()

                return output.array

    # HANDLE STREAM FRAMES

    def wait_for_camera(self, timeout=5):
        """Wait for camera object, with 5 second timeout."""
        timeout_time = time.time() + timeout
        while not self.camera:
            if time.time() > timeout_time:
                raise TimeoutError("Timeout waiting for camera")
            else:
                pass

    def frames(self):
        """
        Create generator that returns frames from the camera.

        Records video from port 1 to a byte stream,
        and iterates sequential frames.
        """
        # Run this initialisation method
        self.initialisation()
        self.wait_for_camera()

        # Start stream recording (and set resolution)
        self.start_stream_recording()

        logging.debug("STREAM ACTIVE")

        # While the iterator is not closed
        try:
            while True:
                # reset stream for next frame
                self.stream.seek(0)
                self.stream.truncate()
                # to stream, read the new frame
                time.sleep(1 / self.camera.framerate * 0.1)
                # yield the result to be read
                frame = self.stream.getvalue()

                # ensure the size of package is right
                if len(frame) == 0:
                    pass
                else:
                    yield frame
        # When GeneratorExit or StopIteration raised, run cleanup code
        finally:
            # Stop stream recording (and set resolution)
            self.stop_stream_recording()

            logging.debug("FRAME ITERATOR END")
