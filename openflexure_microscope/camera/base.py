# -*- coding: utf-8 -*-
import time
import os
import threading
import datetime
import logging

try:
    from greenlet import getcurrent as get_ident
except ImportError:
    try:
        from thread import get_ident
    except ImportError:
        from _thread import get_ident

from .capture import CaptureObject, BASE_CAPTURE_PATH, TEMP_CAPTURE_PATH
from openflexure_microscope.utilities import entry_by_id
from openflexure_microscope.lock import StrictLock


def last_entry(object_list: list):
    """Return the last entry of a list, if the list contains items."""
    if object_list:  # If any images have been captured
        return object_list[-1]  # Return the latest captured image
    else:
        return None


def generate_basename():
    """Return a default filename based on the capture datetime"""
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def generate_numbered_basename(obj_list: list) -> str:
    initial_basename = generate_basename()
    basename = initial_basename
    # Handle clashing
    iterator = 1
    while basename in [obj.basename for obj in obj_list]:
        basename = initial_basename + "_{}".format(iterator)
        iterator += 1

    return basename


class CameraEvent(object):
    """
    A frame-signaller object used by any instances or subclasses of BaseCamera.

    An event-like class that signals all active clients when a new frame is available.
    """
    def __init__(self):
        self.events = {}

    def wait(self, timeout: int = 5):
        """Wait for the next frame (invoked from each client's thread)."""
        ident = get_ident()
        if ident not in self.events:
            # this is a new client
            # add an entry for it in the self.events dict
            # each entry has two elements, a threading.Event() and a timestamp
            self.events[ident] = [threading.Event(), time.time()]
        return self.events[ident][0].wait(timeout)

    def set(self):
        """Signal that a new frame is available."""
        now = time.time()
        remove = None
        for ident, event in self.events.items():
            if not event[0].isSet():
                # if this client's event is not set, then set it
                # also update the last set timestamp to now
                event[0].set()
                event[1] = now
            else:
                # if the client's event is already set, it means the client
                # did not process a previous frame
                # if the event stays set for more than 5 seconds, then assume
                # the client is gone and remove it
                if now - event[1] > 5:
                    remove = ident
        if remove:
            del self.events[remove]

    def clear(self):
        """Clear frame event, once processed."""
        self.events[get_ident()][0].clear()


class BaseCamera(object):
    """
    Base implementation of StreamingCamera.

    Attributes:
        thread: Background thread reading frames from camera
        camera: Camera object
        lock (:py:class:`openflexure_microscope.lock.StrictLock`): Strict lock controlling thread
            access to stage hardware
        frame (bytes): Current frame is stored here by background thread
        last_access (time): Time of last client access to the camera
        stream_timeout (int): Number of inactive seconds before timing out the stream
        stream_timeout_enabled (bool): Enable or disable timing out the stream
        state (dict): Dictionary for capture state
        config (dict): Dictionary of base camera config
        paths (dict): Dictionary of capture paths
        images (list): List of image capture objects
        videos (list): List of video capture objects
    """
    def __init__(self):
        self.thread = None
        self.camera = None 

        self.lock = StrictLock(timeout=1)

        self.frame = None
        self.last_access = 0
        self.event = CameraEvent()

        self.stream_timeout = 20
        self.stream_timeout_enabled = False

        self.state = {}
        self.config = {}
        self.paths = {
            'image': BASE_CAPTURE_PATH,
            'video': BASE_CAPTURE_PATH,
            'image_tmp': TEMP_CAPTURE_PATH,
            'video_tpm': TEMP_CAPTURE_PATH
        } 

        # Capture data
        self.images = []
        self.videos = []

    def apply_config(self, config):
        """Update settings from a config dictionary"""
        self.config.update(config)

    def read_config(self, config):
        """Return the current settings as a dictionary"""
        return self.config

    def __enter__(self):
        """Create camera on context enter."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close camera stream on context exit."""
        self.close()

    def close(self):
        """Close the BaseCamera and all attached StreamObjects."""
        logging.info("Closing {}".format(self))
        # Close all StreamObjects
        for capture_list in [self.images, self.videos]:
            for stream_object in capture_list:
                stream_object.close()
        # Stop worker thread
        self.stop_worker()
        logging.info("Closed {}".format(self))

    def wait_for_camera(self, timeout=5):
        """Wait for camera object, with 5 second timeout."""
        timeout_time = time.time() + timeout
        while not self.camera:
            if time.time() > timeout_time:
                raise TimeoutError("Timeout waiting for camera")
            else:
                pass

    # START AND STOP WORKER THREAD

    def start_worker(self, timeout: int = 5) -> bool:
        """Start the background camera thread if it isn't running yet."""
        timeout_time = time.time() + timeout

        self.last_access = time.time()
        self.stop = False
        
        if not self.state['stream_active']:
            # start background frame thread
            self.thread = threading.Thread(target=self._thread)
            self.thread.daemon = True
            self.thread.start()

            # wait until frames are available
            logging.info("Waiting for frames")
            while self.get_frame() is None:
                if time.time() > timeout_time:
                    raise TimeoutError("Timeout waiting for frames.")
                else:
                    time.sleep(0.1)
        return True

    def stop_worker(self, timeout: int = 5) -> bool:
        """Flag worker thread for stop. Waits for thread close or timeout."""
        logging.debug("Stopping worker thread")
        timeout_time = time.time() + timeout

        if self.state['stream_active']:
            self.stop = True
            self.thread.join()  # Wait for stream thread to exit
            logging.debug("Waiting for stream thread to exit.")

        while self.state['stream_active']:
            if time.time() > timeout_time:
                logging.debug("Timeout waiting for worker thread close.")
                raise TimeoutError("Timeout waiting for worker thread close.")
            else:
                time.sleep(0.1)
        return True

    # HANDLE STREAM FRAMES

    def get_frame(self):
        """Return the current camera frame."""
        self.last_access = time.time()

        # wait for a signal from the camera thread
        self.event.wait()
        self.event.clear()

        return self.frame

    def frames(self):
        """Create generator that returns frames from the camera."""
        raise RuntimeError('Must be implemented by subclasses.')

    # RETURNING CAPTURES

    @property
    def image(self):
        """Return the latest captured image."""
        return last_entry(self.images)

    @property
    def video(self):
        """Return the latest recorded video."""
        return last_entry(self.videos)

    def image_from_id(self, image_id):
        """Return an image StreamObject with a matching ID."""
        return entry_by_id(image_id, self.images)

    def video_from_id(self, video_id):
        """Return a video StreamObject with a matching ID."""
        return entry_by_id(video_id, self.videos)

    # CREATING NEW CAPTURES

    def shunt_captures(self, target_list: list):
        for obj in target_list:  # For each older capture
            obj.shunt()  # Shunt capture from memory to storage

    def new_image(
            self,
            write_to_file: bool = True,
            temporary: bool = True,
            filename: str = None,
            folder: str = "",
            fmt: str = 'jpeg'):

        """
        Create a new image capture object. Adds to the image list, and shunt all others.

        Args:
            write_to_file (bool): Should the StreamObject write to a file, or an in-memory byte stream.
            temporary (bool): Should the data be deleted after session ends. 
                Creating the capture with a content manager sets this to true.
            filename (str): Name of the stored file. Defaults to timestamp.
            fmt (str): Format of the capture.
        """

        # Generate file name
        if not filename:
            filename = generate_numbered_basename(self.images)
            logging.debug(filename)
        filename = "{}.{}".format(filename, fmt)

        # Generate folder
        base_folder = self.paths['image_tmp'] if temporary else self.paths['image']
        folder = os.path.join(base_folder, folder)

        # Generate file path
        filepath = os.path.join(folder, filename)

        # Create capture object
        output = CaptureObject(
            write_to_file=write_to_file,
            temporary=temporary,
            filepath=filepath)

        # Update capture list
        self.shunt_captures(self.images)
        self.images.append(output)

        return output

    def new_video(
            self,
            write_to_file: bool = True,
            temporary: bool = False,
            filename: str = None,
            folder: str = "",
            fmt: str = 'h264'):

        """
        Create a new video capture object. Adds to the image list, and shunt all others.

        Args:
            write_to_file (bool): Should the StreamObject write to a file, or an in-memory byte stream.
            temporary (bool): Should the data be deleted after session ends. 
                Creating the capture with a content manager sets this to true.
            filename (str): Name of the stored file. Defaults to timestamp.
            fmt (str): Format of the capture.
        """

        # Generate file name
        if not filename:
            filename = generate_numbered_basename(self.videos)
            logging.debug(filename)
        filename = "{}.{}".format(filename, fmt)

        # Generate folder
        base_folder = self.paths['video_tmp'] if temporary else self.paths['video']
        folder = os.path.join(base_folder, folder)

        # Generate file path
        filepath = os.path.join(folder, filename)

        # Create capture object
        output = CaptureObject(
            write_to_file=write_to_file,
            temporary=temporary,
            filepath=filepath)

        # Update capture list
        self.shunt_captures(self.videos)
        self.videos.append(output)

        return output

    # WORKER THREAD

    def _thread(self):
        """Camera background thread."""
        self.frames_iterator = self.frames()
        logging.debug("Entering worker thread.")

        self.state['stream_active'] = True

        for frame in self.frames_iterator:
            self.frame = frame
            self.event.set()  # send signal to clients
            time.sleep(0)

            # Handle timeout
            if (
                self.stream_timeout_enabled and  # If using timeout
                (time.time() - self.last_access > self.stream_timeout) and  # And timeout time
                not self.state['preview_active']  # And GPU preview is not active
            ):
                self.frames_iterator.close()
                break

            try:
                if self.stop is True:
                    logging.debug("Worker thread flagged for stop.")
                    self.frames_iterator.close()
                    break

            except AttributeError:
                pass

        logging.debug("BaseCamera worker thread exiting...")
        # Set stream_activate state
        self.state['stream_active'] = False
