# -*- coding: utf-8 -*-

"""
Raspberry Pi camera implementation of the StreamingCamera class.

NOTES:
Still port used for image capture
Preview port reserved for onboard GPU preview
Video port:
    Splitter port 0: Image capture (if use_video_port == True)
    Splitter port 1: Streaming frames
    Splitter port 2: Video capture
    Splitter port 3: [Currently unused]

StreamingCamera streams at stream_resolution
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
import logging

# Pi camera
import picamera
import picamera.array

# Type hinting
from typing import Tuple

from .base import BaseCamera, CaptureObject
# Richard's fix gain
from .set_picamera_gain import set_analog_gain, set_digital_gain

# Handle config and picamera settings
CONFIG_KEYS = {
    'stream_resolution': (832, 624),
    'image_resolution': (2592, 1944),  # Default for PiCamera v1. Overridden in __init__
    'numpy_resolution': (1312, 976),
    'jpeg_quality': 75,
    'picamera_settings': {
        'exposure_mode': None,
        'awb_mode': None,
        'awb_gains': None,
        'framerate': None,
        'shutter_speed': None,
        'saturation': None,
        'analog_gain': None,
        'digital_gain': None,
        'lens_shading_table': None,
    },
}


# MAIN CLASS
class StreamingCamera(BaseCamera):
    """Raspberry Pi camera implementation of StreamingCamera.

    Args:
        config (dict): Dictionary of config parameters to apply on init. If None, will default to basic config.
    """
    def __init__(self, config: dict = None):
        global CONFIG_KEYS

        # Run BaseCamera init
        BaseCamera.__init__(self)
        # Attach to Pi camera
        self.camera = picamera.PiCamera()  #: :py:class:`picamera.PiCamera`: Picamera object

        # Store state of StreamingCamera
        self.state.update({
            'stream_active': False,
            'record_active': False,
            'preview_active': False,
        })
        # Reset variable states
        self.set_zoom(1.0)

        # Populate config and settings with all available keys
        self.config.update(CONFIG_KEYS)

        # Update config based on PiCamera parameters
        self.config.update({
            'image_resolution': tuple(self.camera.MAX_RESOLUTION)
        })

        # Load config dictionary if passed
        if config:
            self.apply_config(config)

        # Create an empty stream
        self.stream = io.BytesIO()

        # Start streaming
        self.start_worker()

    def initialisation(self):
        """Run any initialisation code when the frame iterator starts."""
        pass

    def close(self):
        """Close the Raspberry Pi StreamingCamera."""
        # Run BaseCamera close method
        BaseCamera.close(self)
        # Detach Pi camera
        if self.camera:
            self.camera.close()

    # HANDLE SETTINGS
    @property
    def supports_lens_shading(self):
        """Determine whether the picamera module supports lens shading.

        As of March 2018, picamera did not wrap the necessary MMAL commands to
        set the lens shading table, or to write the value of analog or digital
        gain.  I have a forked version of the library that does support these.
        For ease of use by people who don't want those features, this library
        does not have a hard dependency on lens shading.  However, we need to
        check in some places whether it's available.
        """
        return hasattr(self.camera, "lens_shading_table")

    def read_config(self):
        """
        Return config dictionary of the StreamingCamera.
        """
        conf_dict = {
            'picamera_settings': {},
        }

        # PiCamera parameters (obtained directly from PiCamera object)
        for key, _ in CONFIG_KEYS['picamera_settings'].items():
            try:
                value = getattr(self.camera, key)
                conf_dict['picamera_settings'][key] = value
            except AttributeError:
                logging.debug("Unable to read PiCamera attribute {}".format(key))

        # StreamingCamera parameters (obtained from StreamingCamera _config)
        for key in CONFIG_KEYS:
            if (key != 'picamera_settings') and (key in self.config):
                conf_dict[key] = self.config[key]

        return conf_dict

    def apply_config(self, config: dict) -> None:
        """
        Write a config dictionary to the StreamingCamera config.

        The passed dictionary may contain other parameters not relevant to
        camera config. Eg. Passing a general config file will work fine.

        Args:
            config (dict): Dictionary of config parameters.
        """
        
        paused_stream = False

        with self.lock:

            # Apply valid config params to Picamera object
            if not self.state['record_active']:  # If not recording a video

                logging.debug("Applying config:")
                logging.debug(config)

                # Pause stream while changing settings
                if self.state['stream_active']:  # If stream is active
                    logging.info("Pausing stream to update config.")
                    self.stop_stream_recording()  # Pause stream
                    paused_stream = True  # Remember to unpause stream when done

                # PiCamera parameters (applied directly to PiCamera object)
                if 'picamera_settings' in config:  # If new settings are given
                    for key, value in config['picamera_settings'].items():  # For each given setting
                        if hasattr(self.camera, key):
                            self.config['picamera_settings'][key] = None  # Add the key to the list of returned settings
                            logging.debug("Setting parameter {}: {}".format(key, config['picamera_settings'][key]))

                            # Handle special attributes:
                            if key == 'digital_gain':
                                set_digital_gain(self.camera, value)
                            elif key == 'analog_gain':
                                set_analog_gain(self.camera, value)
                            elif key == "shutter_speed":
                                # TODO: use types from CONFIG_KEYS? @jtc42
                                self.camera.shutter_speed = int(value)
                            else:
                                setattr(self.camera, key, value)  # Write setting to camera

                # StreamingCamera parameters (applied via StreamingCamera config)
                for key, value in config.items():  # For each provided setting
                    if key != 'picamera_settings':  # We already handled this
                        if key not in CONFIG_KEYS.keys():
                            logging.warn("{} is not in the streaming camera settings dictionary - adding it.")
                            #continue #TODO: filter settings somehow?
                        logging.debug("Setting parameter {}: {}".format(key, value))
                        self.config[key] = value

                # If stream was paused to update config, unpause
                if paused_stream:
                    logging.info("Resuming stream.")
                    self.start_stream_recording()

            else:
                raise Exception(
                    "Cannot update camera config while recording is active.")

    def set_zoom(self, zoom_value: float = 1.) -> None:
        """
        Change the camera zoom, handling re-centering and scaling.
        """
        with self.lock:
            self.state['zoom_value'] = float(zoom_value)
            if self.state['zoom_value'] < 1:
                self.state['zoom_value'] = 1
            # Richard's code for zooming !
            fov = self.camera.zoom
            centre = np.array([fov[0] + fov[2]/2.0, fov[1] + fov[3]/2.0])
            size = 1.0/self.state['zoom_value']
            # If the new zoom value would be invalid, move the centre to
            # keep it within the camera's sensor (this is only relevant
            # when zooming out, if the FoV is not centred on (0.5, 0.5)
            for i in range(2):
                if np.abs(centre[i] - 0.5) + size/2 > 0.5:
                    centre[i] = 0.5 + (1.0 - size)/2 * np.sign(centre[i]-0.5)
            logging.info("setting zoom, centre {}, size {}".format(centre, size))
            new_fov = (centre[0] - size/2, centre[1] - size/2, size, size)
            self.camera.zoom = new_fov

    # LAUNCH ACTIONS

    def start_preview(self, fullscreen=True, window=None) -> bool:
        """Start the on board GPU camera preview."""
        logging.info("Starting the GPU preview")

        # TODO: Commented out as I honestly can't remember why this was here. May need to put back?
        # self.start_stream_recording()

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
            self.state['preview_active'] = True
        except picamera.exc.PiCameraMMALError as e:
            logging.error("Suppressed a MMALError in start_preview. Exception: {}".format(e))
        except picamera.exc.PiCameraValueError as e:
            logging.error("Suppressed a ValueError exception in start_preview. Exception: {}".format(e))

    def stop_preview(self) -> bool:
        """Stop the on board GPU camera preview."""
        self.camera.stop_preview()
        self.state['preview_active'] = False

    def start_recording(
            self,
            output,
            fmt: str = 'h264',
            quality: int = 15):
        """Start recording.

        Start a new video recording, writing to a output object.

        Args:
            output (CaptureObject/str): Output object to write data bytes to.
            fmt (str): Format of the capture.
            quality (int): Video recording quality.

        Returns:
            output_object (str/BytesIO): Target object.

        """
        with self.lock:
            # Start recording method only if a current recording is not running
            if not self.state['record_active']:

                # If output is a StreamObject
                if isinstance(output, CaptureObject):
                    # Lock the StreamObject while recording
                    output.lock()
                    # Set target to capture stream
                    output_stream = output.stream
                else:
                    output_stream = output

                # Start the camera video recording on port 2
                logging.info("Recording to {}".format(output))

                self.camera.start_recording(
                    output_stream,
                    format=fmt,
                    splitter_port=2,
                    resize=self.config['stream_resolution'],
                    quality=quality)

                # Update state dictionary
                self.state['record_active'] = True

                return output

            else:
                logging.error(
                    "Cannot start a new recording\
                    until the current recording has stopped.")
                return None

    def stop_recording(self):
        """Stop the last started video recording on splitter port 2."""
        with self.lock:
            # Stop the camera video recording on port 2
            logging.info("Stopping recording")
            self.camera.stop_recording(splitter_port=2)
            logging.info("Recording stopped")

            # Update state dictionary
            self.state['record_active'] = False

    def stop_stream_recording(
            self,
            splitter_port: int = 1,
            resolution: Tuple[int, int] = None) -> None:
        """
        Sets the camera resolution to the still-image resolution, and stops recording if the stream is active.

        Args:
            splitter_port (int): Splitter port to stop recording on
            resolution ((int, int)): Resolution to set the camera to, after stopping recording.
        """
        with self.lock:
            # If no resolution is specified, default to image_resolution
            if not resolution:
                resolution = self.config['image_resolution']

            # Stop the camera video recording on port 1
            try:
                self.camera.stop_recording(splitter_port=splitter_port)
            except picamera.exc.PiCameraNotRecording:
                logging.info("Not recording on splitter_port {}".format(splitter_port))
            else:
                logging.info("Stopped MJPEG stream on port {1}. Switching to {0}.".format(resolution, splitter_port))

            # Increase the resolution for taking an image
            time.sleep(0.2)  # Sprinkled a sleep to prevent camera getting confused by rapid commands
            self.camera.resolution = resolution

    def start_stream_recording(
            self,
            splitter_port: int = 1,
            resolution: Tuple[int, int] = None) -> None:
        """
        Sets the camera resolution to the video/stream resolution, and starts recording if the stream should be active.

        Args:
            splitter_port (int): Splitter port to start recording on
            resolution ((int, int)): Resolution to set the camera to, before starting recording. 
                Defaults to `self.config['stream_resolution']`.
        """
        with self.lock:
            # If stream object was destroyed
            if not hasattr(self, 'stream'):
                self.stream = io.BytesIO()  # Create a stream object

            # If no explicit resolution is passed
            if not resolution:
                resolution = self.config['stream_resolution']  # Default to video recording resolution

            # Reduce the resolution for video streaming
            try:
                self.camera._check_recording_stopped()
            except picamera.exc.PiCameraRuntimeError:
                logging.info("Error while changing resolution: Recording already running.")
            else:
                self.camera.resolution = resolution

            # If the stream should be active
            if self.state['stream_active']:
                try:
                    # Start recording on stream port
                    self.camera.start_recording(
                        self.stream,
                        format='mjpeg',
                        quality=self.config['jpeg_quality'],
                        bitrate=-1,  # RWB: disable bitrate control 
                        # (bitrate control makes JPEG size less good as a focus
                        # metric)
                        splitter_port=splitter_port)
                except picamera.exc.PiCameraAlreadyRecording:
                    logging.info("Error while starting preview: Recording already running.")
                else:
                    logging.debug("Started MJPEG stream at {} on port {}".format(resolution, splitter_port))

    def capture(
            self,
            output,
            fmt: str = 'jpeg',
            use_video_port: bool = False,
            resize: Tuple[int, int] = None,
            bayer: bool = True):
        """
        Capture a still image to a StreamObject.

        Defaults to JPEG format.
        Target object can be overridden for development purposes.

        Args:
            output (CaptureObject/str): Output object to write data bytes to.
            use_video_port (bool): Capture from the video port used for streaming. Lower resolution, faster.
            fmt (str): Format of the capture.
            resize ((int, int)): Resize the captured image.
            bayer (bool): Store raw bayer data in capture
        """

        with self.lock:
            # If output is a StreamObject
            if isinstance(output, CaptureObject):
                # Set target to capture stream
                output_stream = output.stream
            else:
                output_stream = output

            logging.info("Capturing to {}".format(output))

            # Set resolution and stop stream recording if necessary
            if not use_video_port:
                self.stop_stream_recording()

            self.camera.capture(
                output_stream,
                format=fmt,
                quality=100,
                resize=resize,
                bayer=(not use_video_port) and bayer,
                use_video_port=use_video_port)

            # Set resolution and start stream recording if necessary
            if not use_video_port:
                self.start_stream_recording()

            return output

    def yuv(
            self,
            use_video_port: bool = True,
            resize: Tuple[int, int] = None) -> np.ndarray:
        """Capture an uncompressed still YUV image to a Numpy array.

        Args:
            use_video_port (bool): Capture from the video port used for streaming. Lower resolution, faster.
            resize ((int, int)): Resize the captured image.
        """
        with self.lock:
            if use_video_port:
                resolution = self.config['stream_resolution']
            else:
                resolution = self.config['numpy_resolution']

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
                    output,
                    resize=size,
                    format='yuv',
                    use_video_port=use_video_port)

                if not use_video_port:
                    self.start_stream_recording()

                return output.array

    def array(
            self,
            use_video_port: bool = True,
            resize: Tuple[int, int] = None) -> np.ndarray:
        """Capture an uncompressed still RGB image to a Numpy array.

        Args:
            use_video_port (bool): Capture from the video port used for streaming. Lower resolution, faster.
            resize ((int, int)): Resize the captured image.
        """
        with self.lock:
            if use_video_port:
                resolution = self.config['stream_resolution']
            else:
                resolution = self.config['numpy_resolution']

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
                    output,
                    resize=size,
                    format='rgb',
                    use_video_port=use_video_port)

                # Resume stream
                self.start_stream_recording()

                return output.array

    # HANDLE STREAM FRAMES

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

        # Update state
        logging.debug("STREAM ACTIVE")

        # While the iterator is not closed
        try:
            while True:
                # reset stream for next frame
                self.stream.seek(0)
                self.stream.truncate()
                # to stream, read the new frame
                time.sleep(1/self.camera.framerate*0.1)
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
