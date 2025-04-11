# ruff: noqa: E722

import shutil
import zipfile
import threading
from typing import Optional, Mapping
from fastapi import HTTPException
from fastapi.responses import FileResponse
import numpy as np
import os
import time
from PIL import Image
from pydantic import BaseModel
from datetime import datetime
from subprocess import CompletedProcess, Popen, PIPE, SubprocessError, STDOUT
from threading import Event
import glob
import json
import piexif

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.invocation import (
    CancelHook,
    InvocationLogger,
    InvocationCancelledError,
)
from labthings_fastapi.decorators import thing_action, thing_property, fastapi_endpoint
from labthings_fastapi.outputs.blob import blob_type
from .camera import CameraDependency as CamDep
from .stage import StageDependency as StageDep

from openflexure_microscope_server.utilities import ErrorCapturingThread
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper
from openflexure_microscope_server.things.background_detect import BackgroundDetectThing


CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")
BackgroundDep = direct_thing_client_dependency(
    BackgroundDetectThing, "/background_detect/"
)


def closest(current, focused_path):
    """Finds the index of the closest x-y position in a list from the current position,
    with ties split by the later element in the list (most recently taken)

    must be float64 to deal with the huge numbers involved!"""

    current_pos = np.array(current[:2], dtype="float64")
    path_pos = np.asarray(focused_path, dtype="float64").T[:2].T

    dist_2 = np.sqrt(
        np.sum((path_pos - current_pos) ** 2, axis=1, dtype="float64"), dtype="float64"
    )
    min_dist = np.argmin(dist_2)
    mask = np.where(dist_2 == dist_2[min_dist], 1, 0)
    try:
        closest = np.max(np.nonzero(mask))
    except:
        closest = 0
    return closest


def unpack_autofocus(scan_data):
    """Extract z, sharpness data from a move_and_measure call

    Data will start at `start_index`, i.e. `start_index` points are dropped
    from the beginning of the array.
    """
    jpeg_times = scan_data["jpeg_times"]
    jpeg_sizes = scan_data["jpeg_sizes"]
    jpeg_sizes_mb = [x / 10**3 for x in jpeg_sizes]
    stage_times = scan_data["stage_times"]
    stage_positions = scan_data["stage_positions"]
    stage_height = [pos[2] for pos in stage_positions]

    jpeg_heights = np.interp(jpeg_times, stage_times, stage_height)

    def turningpoints(lst):
        dx = np.diff(lst)
        return dx[1:] * dx[:-1] < 0

    turning = np.where(turningpoints(jpeg_heights))[0] + 1

    return jpeg_heights[turning[0] : turning[1]], jpeg_sizes_mb[turning[0] : turning[1]]


def limit_focus_change(prev_pos, prev_z, new_pos, new_z, limit):
    # limit is the largest ratio of change in z to change in xy that's allowed

    prev_xy = np.asarray(prev_pos, dtype="float64")
    new_xy = np.asarray(new_pos, dtype="float64")

    dist = np.sqrt(np.sum(((new_xy - prev_xy) / 10**4) ** 2, dtype="float64"))

    focus_change = abs(new_z - prev_z) / 10**4
    if dist == 0:
        print(f"Not moved between {prev_pos} and {new_pos}")
        movement_ratio = 0
    else:
        movement_ratio = np.divide(focus_change, dist, dtype="float64")

    if movement_ratio > limit:
        return "reject"
    else:
        return "accept"


def steps_from_centre(current_loc, starting_loc, dx, dy):
    step_size = np.array([dx, dy])
    return np.max(np.abs(np.divide(np.subtract(current_loc, starting_loc), step_size)))


def distance_to_site(current_pos, next_pos):
    next_pos = np.array(next_pos, dtype="float64")
    current_pos = np.array(current_pos, dtype="float64")
    return np.sqrt(
        (next_pos[1] - current_pos[1]) ** 2 + (next_pos[0] - current_pos[0]) ** 2
    )


class NotEnoughFreeSpaceError(IOError):
    pass


def ensure_free_disk_space(path: str, min_space: int = 500000000) -> None:
    """Raise an exception if we are running out of disk space"""
    du = shutil.disk_usage(path)
    if du.free < min_space:
        raise NotEnoughFreeSpaceError(
            "There is not enough free disk space to continue."
            f"(Required: {min_space}, {du})."
        )


class ScanInfo(BaseModel):
    """ "Summary information about a scan folder"""

    name: str
    created: datetime
    modified: datetime
    number_of_images: int


DOWNLOADABLE_SCAN_FILES = ("images.zip",)

JPEGBlob = blob_type("image/jpeg")
ZipBlob = blob_type("application/zip")
IMG_DIR_NAME = "images"

SCAN_ZERO_PAD_DIGITS = 4


def _scan_running(method):
    """
    This decorator is used by all methods in SmartScanThing that are using
    the variables set for the scan. It will throw a runtime error if
    self._scan_logger is not set, as all scan variables are set at
    the same time and released with the lock
    """

    def scan_running_wrapper(self, *args, **kwargs):
        # Only start the method is the scan logger is set
        if self._scan_logger is not None:
            return method(self, *args, **kwargs)
        raise RuntimeError(
            "Calling a @scan_running method can only be done while a scan is running!"
        )

    return scan_running_wrapper


class SmartScanThing(Thing):
    def __init__(self, path_to_openflexure_stitch: str):
        self._stitching_script = path_to_openflexure_stitch
        self._preview_stitch_popen = None
        self._preview_stitch_popen_lock = threading.Lock()
        self._correlate_popen = None
        self._correlate_popen_lock = threading.Lock()
        self._scan_lock = threading.Lock()

        # Variables set by the scan
        self._latest_scan_name: Optional[str] = None

        # Scan logger is the invocation logger labthings-fastapi creates
        # when the `sample_scan` thing_action is called. It is saved as
        # private class variable along with many others here.
        # Access to these variables requires a scan to be running,
        # any method that calls these should be decorrected with
        # @_scan_running
        self._scan_logger: Optional[InvocationLogger] = None
        self._cancel: Optional[CancelHook] = None
        self._autofocus: Optional[AutofocusDep] = None
        self._stage: Optional[StageDep] = None
        self._cam: Optional[CamDep] = None
        self._metadata_getter: Optional[GetThingStates] = None
        self._csm: Optional[CSMDep] = None
        self._background_detect: Optional[BackgroundDep] = None
        self._ongoing_scan_name: Optional[str] = None
        self._starting_position: Optional[Mapping[str, int]] = None
        self._scan_images_taken: Optional[int] = None

    @thing_action
    def sample_scan(
        self,
        cancel: CancelHook,
        logger: InvocationLogger,
        autofocus: AutofocusDep,
        stage: StageDep,
        cam: CamDep,
        metadata_getter: GetThingStates,
        csm: CSMDep,
        background_detect: BackgroundDep,
        scan_name: str = "",
    ):
        """Move the stage to cover an area, taking images that can be tiled together.

        The stage will move in a pattern that grows outwards from the starting point,
        stopping once it is surrounded by "background" (as detected by the
        background_detect Thing).
        """

        started_scan = False
        got_lock = self._scan_lock.acquire(timeout=0.1)
        if not got_lock:
            raise RuntimeError("Trying to run scan while scan is already running!")

        # Set private variables for this scan
        self._cancel = cancel
        self._scan_logger = logger
        self._autofocus = autofocus
        self._stage = stage
        self._cam = cam
        self._metadata_getter = metadata_getter
        self._csm = csm
        self._background_detect = background_detect
        self._scan_images_taken = 0

        try:
            self._check_background_is_set()
            self._ongoing_scan_name = self._get_unique_scan_name_and_dir(scan_name)
            overlap = self.overlap
            # record starting position so we can return there
            self._starting_position = self._stage.position
            started_scan = True
            self._run_scan(scan_name, overlap)
        except Exception as e:
            if started_scan:
                self._return_to_starting_position()
                if not isinstance(e, NotEnoughFreeSpaceError):
                    # Don't stich if drive is full (already logged)
                    self._perform_final_stitch(overlap)
            # Error must be raised so UI gives correct output
            raise e
        finally:
            # However the scan finishes unset all variables and release lock
            self._cancel = None
            self._scan_logger = None
            self._autofocus = None
            self._stage = None
            self._cam = None
            self._metadata_getter = None
            self._csm = None
            self._background_detect = None
            self._ongoing_scan_name = None
            self._scan_images_taken = None
            self._scan_lock.release()

    @_scan_running
    def _check_background_is_set(self):
        """Before starting a scan check that we've got a background set

        Raise error if it is not set but background detect is being used.
        """

        if self.skip_background:
            if not self._background_detect.background_distributions:
                raise RuntimeError(
                    "Background is not set: you need to calibrate background detection."
                )
        else:
            self._scan_logger.warning(
                "This scan will run in a spiral from the starting point "
                f"until you cancel it, or until it has moved by {self.max_range} steps "
                "in every direction. Make sure you watch it run to stop it leaving "
                "the area of interest, or (worse) leading the microscope's range "
                "of motion."
            )

    @property
    def base_scan_dir(self) -> str:
        """This directory will hold all the scans we do."""
        # TODO: This should be determined using sensible configuration.
        # If the working directory is `/var/openflexure` this will result
        # in scans being saved at `/var/openflexure/scans/`
        return "scans"

    @thing_property
    def latest_scan_name(self) -> Optional[str]:
        """The name of the last scan to be started."""
        return self._latest_scan_name

    def dir_for_scan(self, scan_name: str):
        """The path to the scan directory for scan with input name"""
        return os.path.join(self.base_scan_dir, scan_name)

    def images_dir_for_scan(self, scan_name: str) -> str:
        """The path to the images directory for scan with input name"""
        scan_dir = self.dir_for_scan(scan_name=scan_name)
        return os.path.join(scan_dir, IMG_DIR_NAME)

    @property
    @_scan_running
    def _ongoing_scan_dir(self):
        """For the ongoing scan this returns the scan directory"""
        if not self._ongoing_scan_name:
            raise RuntimeError("Cannot get ongoing scan name while no scan is running")
        return self.dir_for_scan(self._ongoing_scan_name)

    @property
    @_scan_running
    def _ongoing_scan_images_dir(self):
        """For the ongoing scan this returns the image directory"""
        if not self._ongoing_scan_name:
            raise RuntimeError("Cannot get ongoing scan name while no scan is running")
        return self.images_dir_for_scan(self._ongoing_scan_name)

    @_scan_running
    def _get_unique_scan_name_and_dir(self, scan_name: str) -> str:
        """Get a unique name for this scan and create a directory for it

        The scan will be named `{scan_name}_0001` where the number is
        zero-padded to be 4 digits long (to allow correct sorting if the
        scans are ordered alphanumerically).

        Note that if you have discontinuous numbering (e.g. you've got scans
        numbered 1 through 10, but you deleted scan 5), then the gaps will
        get filled in - so there's no guarantee, for now, that the numbers
        will correspond to order of creation. This may change in the future.

        Creates a new empty folder, into which scans are saved

        Returns the scan name.

        The directory can be accessed by self.dir_for_scan(unique_scan_name)

        """
        if not os.path.exists(self.base_scan_dir):
            os.makedirs(self.base_scan_dir)

        # if no scan name is set set to "scan". This done here as empty strings
        # get passed in otherwise.
        if not scan_name:
            scan_name = "scan"

        # Set a sensible limit for the number of scans of one name
        # based on our zero padding.
        max_scan_no = 10**SCAN_ZERO_PAD_DIGITS - 1

        for j in range(max_scan_no):
            trial_unique_scan_name = f"{scan_name}_{j:0{SCAN_ZERO_PAD_DIGITS}d}"
            trial_dir = self.dir_for_scan(trial_unique_scan_name)
            if not os.path.exists(trial_dir):
                os.makedirs(trial_dir)
                # If we made the directory this is the scan name
                # Save it as the most latest scan (this persists as a
                # property after the scan finishes)
                self._latest_scan_name = trial_unique_scan_name
                # Return the scan name
                return trial_unique_scan_name
        raise FileExistsError("Could not create a new scan folder: all names in use!")

    @_scan_running
    def _move_to_next_point(
        self,
        path: list[list[int]],
        focused_path: list[list[int]],
    ) -> list[int]:
        """Remove the first point from the path, and move there.

        This will move to the next XY position in `path`, taking the `z` value
        either from the current z value of the stage, or from `focused_path`.

        Returns the point we have moved to.
        """
        loc = [path[0][0], path[0][1]]
        path.remove(path[0])
        if len(focused_path) > 1:
            z_index = closest(loc, focused_path)
            z = int(focused_path[z_index][2])
        else:
            z = self._stage.position["z"]
        self._scan_logger.info(f"Moving to {loc}")
        self._stage.move_absolute(
            x=int(loc[0]), y=int(loc[1]), z=z - self.autofocus_dz / 2
        )
        return loc + [z]

    @_scan_running
    def _run_scan(self, scan_name, overlap):
        # Define these variables so we can use them in the finally: block
        # (after testing they are not None)
        scan_successful = True
        capture_thread = None

        try:
            os.mkdir(self._ongoing_scan_images_dir)

            self._scan_logger.info(f"Saving images to {self._ongoing_scan_images_dir}")

            max_dist = self.max_range

            if self.autofocus_dz == 0:
                self._scan_logger.info("Running scan without autofocus")
            elif self.autofocus_dz <= 200:
                self._scan_logger.warning(
                    f"Your dz range is {self.autofocus_dz} steps, which is too short to attempt to focus. Running without autofocus"
                )

            names = []
            positions = []

            r = self._cam.grab_jpeg()
            arr = np.array(Image.open(r.open()))
            if self._csm.image_resolution is None:
                raise RuntimeError(
                    "Camera-stage mapping is not calibrated. This is required before "
                    "scans can be carried out."
                )
            if list(arr.shape[:2]) != [int(i) for i in self._csm.image_resolution]:
                self._scan_logger.error(
                    f"Images are, by default, {arr.shape[:2]}, but the CSM was "
                    f"calibrated at {self._csm.image_resolution}."
                )

            # Here, we calculate the x and y step size based on the desired overlap
            # TODO: Consider using CSM calibration size instead
            # TODO: generalise to have 2D displacements for x and y (as the
            # camera and stage may not be aligned).
            csm_disp_matrix = self._csm.image_to_stage_displacement_matrix

            dx = int(
                np.abs(
                    np.dot(
                        np.array([0, arr.shape[1] * (1 - overlap)]), csm_disp_matrix
                    )[0]
                )
            )
            dy = int(
                np.abs(
                    np.dot(
                        np.array([arr.shape[0] * (1 - overlap), 0]), csm_disp_matrix
                    )[1]
                )
            )

            self._scan_logger.info(
                f"Based on an overlap of {overlap}, we will make steps of {dx}, {dy}"
            )

            # construct a 2D scan path
            path = [[self._stage.position["x"], self._stage.position["y"]]]

            focused_path = []  # This holds a list of all points where focus succeeded
            true_path = []  # This holds a list of all points visited

            start_time = time.strftime("%H_%M_%S-%d_%m_%Y")

            data = {
                "scan_name": scan_name,
                "overlap": overlap,
                "autofocus range": self.autofocus_dz,
                "dx": dx,
                "dy": dy,
                "start time": start_time,
                "skipping background": self.skip_background,
            }

            scan_inputs_fname = os.path.join(
                self._ongoing_scan_images_dir, "scan_inputs.json"
            )
            with open(scan_inputs_fname, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            if self._scan_images_taken != 0:
                raise RuntimeError(
                    "_scan_images_taken should be zero before starting scanning"
                )
            # At the start of the loop, we simultaneously capture an image and move to the next scan point.
            # We skip capturing on the first run, because we've not focused yet - and also we skip capturing if
            # it looks like background.
            while len(path) > 0:
                loc = self._move_to_next_point(path=path, focused_path=focused_path)

                if self._scan_images_taken > 3:
                    if not self._preview_stitch_running():
                        self._preview_stitch_start()
                    if self.stitch_automatically:
                        if not self._correlate_running():
                            self._correlate_start(overlap=overlap)

                ensure_free_disk_space(self._ongoing_scan_dir)

                # Check if the image is background
                if self.skip_background:
                    image_is_sample = self._background_detect.image_is_sample()
                else:
                    image_is_sample = True

                # if more than 92% of the image is background, treat it as background and continue
                if not image_is_sample:
                    self._scan_logger.info(
                        f"Skipping {self._stage.position} as it is {round(self._background_detect.background_fraction(), 0)}% background."
                    )
                else:
                    # if not, it's sample. run an autofocus and use the updated height
                    new_pos = [
                        [self._stage.position["x"] - dx, self._stage.position["y"]],
                        [self._stage.position["x"] + dx, self._stage.position["y"]],
                        [self._stage.position["x"], self._stage.position["y"] - dy],
                        [self._stage.position["x"], self._stage.position["y"] + dy],
                    ]
                    for pos in new_pos:
                        if (
                            pos not in [sublist[:2] for sublist in true_path]
                            and pos not in path
                        ):
                            path.append(pos)

                    attempts = 0
                    if self.autofocus_dz > 200:
                        while True:
                            jpeg_zs, jpeg_sizes = self._autofocus.looping_autofocus(
                                dz=self.autofocus_dz, start="base"
                            )
                            current_height = self._stage.position["z"]
                            time.sleep(0.2)
                            autofocus_success = self._autofocus.verify_focus_sharpness(
                                sweep_sizes=jpeg_sizes, camera=CamDep, threshold=0.92
                            )
                            self._scan_logger.info(
                                f"We just tested the focus! Result was {autofocus_success}"
                            )

                            if autofocus_success:
                                # if there have been successful autofocuses in this scan, find the closest one in x-y
                                # test if the change in z between them exceeds a ratio (indicating a failed autofocus)
                                if len(focused_path) > 0:
                                    nearest_focused_site = focused_path[
                                        closest(loc, focused_path)
                                    ]
                                    result = limit_focus_change(
                                        nearest_focused_site[0:2],
                                        nearest_focused_site[-1],
                                        loc[0:2],
                                        current_height,
                                        0.5,
                                    )

                                # if there haven't been any previous autofocuses, we have to assume this one worked
                                else:
                                    result = "accept"
                            else:
                                result = "reject"

                            # if the autofocus worked, add the current position to the list of successful locations
                            if result == "accept":
                                loc = list(self._stage.position.values())
                                focused_path.append(loc)
                                break
                            if attempts >= 3:
                                self._scan_logger.warning(
                                    "Could not autofocus after 3 attempts."
                                )
                                break
                            # if the autofocus was rejected, we return to the height of the closest successful autofocus. not perfect, but better than wandering out of focus
                            self._scan_logger.info(
                                "The focus has shifted further than we expect: retrying."
                            )
                            self._stage.move_absolute(z=int(loc[2]))
                            attempts += 1

                    # Acquire the image in a thread, and continue once it's acquired (i.e. leave saving in the background)
                    if capture_thread:  # wait for the previous capture to be saved, i.e. don't leave more than one image saving in the background
                        wait_start = time.time()
                        thread_was_alive = capture_thread.is_alive()

                        # If the capture thread has thrown an exception it will be raised when join is called,
                        # this will cause the scan to end. If we want to retry captures at a later date
                        # this is where we will need to catch the IOError or CaptureError from the thread.
                        capture_thread.join()
                        time.sleep(0.2)
                        if thread_was_alive:
                            wait_time = time.time() - wait_start
                            self._scan_logger.info(
                                f"Waited {wait_time:.1f}s for the previous capture to finish saving."
                            )

                        # increment capure counter as thread has completed
                        self._scan_images_taken += 1
                    acquired = Event()
                    name = f"image_{loc[0]}_{loc[1]}.jpg"
                    jpeg_path = os.path.join(self._ongoing_scan_images_dir, name)
                    time.sleep(0.2)

                    # Use ErrorCapturingThread intead of Thread. This will raise errors in the calling
                    # thread only when join() is called, allowing us to handle this appropriately.
                    capture_thread = ErrorCapturingThread(
                        target=self._capture_and_save,
                        kwargs={
                            "acquired": acquired,
                            "jpeg_path": jpeg_path,
                        },
                    )
                    capture_thread.start()
                    acquired.wait()  # wait until the image is acquired

                    positions.append(loc[:2])
                    names.append(name)

                # add the current position to the list of all positions visited
                true_path.append(loc)

                temp_path = []

                for i in path:
                    if distance_to_site(i, true_path[0][:2]) < max_dist:
                        temp_path.append(i)
                    else:
                        self._scan_logger.info(
                            f"Rejected moving to {i} as it is out of range"
                        )
                path = temp_path.copy()
                path = sorted(
                    path,
                    key=lambda x: (
                        steps_from_centre(x, true_path[0][:2], dx, dy),
                        distance_to_site(loc[:2], x),
                    ),
                )
                self.create_zip_of_scan(
                    logger=self._scan_logger,
                    scan_name=self._ongoing_scan_name,
                    download_zip=False,
                )

        except InvocationCancelledError:
            scan_successful = False
            self._scan_logger.info("Stopping scan because it was cancelled.")
        except NotEnoughFreeSpaceError as e:
            scan_successful = False
            self._scan_logger.error(
                f"Stopping scan to avoid filling up the disk: {e}",
                exc_info=e,
            )
            raise e
        except Exception as e:
            scan_successful = False
            self._scan_logger.error(
                f"The scan stopped because of an error: {e} "
                "Attempting to stitch and archive the images acquired so far.",
                exc_info=e,
            )
            raise e
        finally:
            if capture_thread:
                # If the capture thread had an error we capture it here
                try:
                    capture_thread.join()
                except Exception as e:
                    # If the thread has already ended due to an exception we will
                    # ignore any exceptions, but if it appeared to be successful
                    # we will log an error.
                    if scan_successful:
                        self._scan_logger.error(
                            "The scan appears to have started successfully, however the final capture raised"
                            f"the following error: {e}."
                            "Attempting to stitch and archive images.",
                            exc_info=e,
                        )

        # This is what happens if the scan completes sucessfully or the
        # user cancels it.
        self._return_to_starting_position()
        self._perform_final_stitch(overlap)

    @_scan_running
    def _return_to_starting_position(self):
        self._scan_logger.info("Returning to starting position.")
        if self._starting_position is not None:
            self._stage.move_absolute(
                **self._starting_position, block_cancellation=True
            )

    @_scan_running
    def _perform_final_stitch(self, overlap):
        """Perform final stitch of the data"""

        if self._scan_images_taken <= 3:
            self._scan_logger.info("Not performing a stitch as 3 or fewer images taken")
            return

        self.create_zip_of_scan(
            logger=self._scan_logger,
            scan_name=self._ongoing_scan_name,
            download_zip=False,
        )
        self._scan_logger.info("Waiting for background processes to finish...")

        self._preview_stitch_wait()
        self._correlate_wait()
        try:
            if self.stitch_automatically:
                self._scan_logger.info("Stitching final image (may take some time)...")
                self.stitch_scan(
                    logger=self._scan_logger,
                    scan_name=self._ongoing_scan_name,
                    overlap=overlap,
                )
        except SubprocessError as e:
            self._scan_logger.error(f"Stitching failed: {e}", exc_info=e)

    @_scan_running
    def _capture_and_save(
        self,
        acquired: Event,
        jpeg_path: str,
    ) -> None:
        """Capture an image and save it to disk

        This will set the event `acquired` once the image has been acquired, so
        that the stage may be moved while it's saved.
        """
        try:
            capture_start = time.time()
            image, metadata = self._capture_image()
        finally:
            # Ensure aquired is set even if capture fails or program will hang forever.
            acquired.set()
        acquisition_time = time.time()
        self._save_capture(jpeg_path, image, metadata)
        save_time = time.time()
        acquisition_duration = round(acquisition_time - capture_start, 1)
        saving_duration = round(save_time - acquisition_time, 1)
        self._scan_logger.debug(
            f"Acquired {jpeg_path} in {acquisition_duration}s then {saving_duration}s saving to disk"
        )

    @_scan_running
    def _capture_image(self) -> tuple[np.ndarray, dict]:
        """Capture an image in memory and return it with metadata
        This will set the event `acquired` once the image has been acquired, so
        that the stage may be moved while it's saved.
        CaptureError raised if the capture fails for any reason
        returns tuple with numpy array of image data, and dict of metadata
        """
        try:
            metadata = self._metadata_getter()
            image = self._cam.capture_array()[..., :3]
        except Exception as e:
            raise CaptureError("An error occurred while capturing") from e
        return image, metadata

    @_scan_running
    def _save_capture(
        self,
        jpeg_path: str,
        image: np.ndarray,
        metadata: dict,
    ) -> None:
        """Saving the captured image and metadata to disk
        logger warning (via InvocationLogger) is raised if metadata is failed to be added
        IOError is raised if the file cannot be saved
        nothing is returned on success"""
        try:
            Image.fromarray(image.astype("uint8"), "RGB").save(
                jpeg_path, quality=95, subsampling=0
            )
            try:
                exif_dict = piexif.load(jpeg_path)
                exif_dict["Exif"][piexif.ExifIFD.UserComment] = json.dumps(
                    metadata
                ).encode("utf-8")
                piexif.insert(piexif.dump(exif_dict), jpeg_path)
            except:
                self._scan_logger.warning(f"Failed to add metadata to {jpeg_path}")
        except Exception as e:
            raise IOError(f"An error occurred while saving {jpeg_path}") from e

    @thing_property
    def max_range(self) -> int:
        """The maximum distance from the centre of the scan before we break"""
        return self.thing_settings.get("max_range", 45000)

    @max_range.setter
    def max_range(self, value: int) -> None:
        self.thing_settings["max_range"] = value

    @thing_property
    def stitch_tiff(self) -> bool:
        """Whether or not to also produce a pyramidal tiff"""
        return self.thing_settings.get("stitch_tiff", False)

    @stitch_tiff.setter
    def stitch_tiff(self, value: bool) -> None:
        self.thing_settings["stitch_tiff"] = value

    @thing_property
    def skip_background(self) -> bool:
        """Whether to detect and skip empty fields of view

        This uses the settings from the `background_detect` Thing.
        """
        return self.thing_settings.get("skip_background", True)

    @skip_background.setter
    def skip_background(self, value: bool) -> None:
        self.thing_settings["skip_background"] = value

    @thing_property
    def autofocus_dz(self) -> int:
        """The z distance to perform an autofocus"""
        return self.thing_settings.get("autofocus_dz", 1000)

    @autofocus_dz.setter
    def autofocus_dz(self, value: int) -> None:
        self.thing_settings["autofocus_dz"] = value

    @thing_property
    def overlap(self) -> float:
        """The z distance to perform an autofocus"""
        return self.thing_settings.get("overlap", 0.45)

    @overlap.setter
    def overlap(self, value: float) -> None:
        self.thing_settings["overlap"] = value

    @thing_property
    def stitch_automatically(self) -> bool:
        """Should we attempt to stitch scans as we go?"""
        return self.thing_settings.get("stitch_automatically", True)

    @stitch_automatically.setter
    def stitch_automatically(self, value: bool) -> None:
        self.thing_settings["stitch_automatically"] = value

    @thing_property
    def scans(self) -> list[ScanInfo]:
        """All the available scans

        Each scan has a name (which can be used to access it), along with
        its modified and created times (according to the filesystem) and
        the number of items in the `images` folder. Note that the number
        of images reported may be confused if non-image files are present
        in the `images` folder.
        """
        scans: list[ScanInfo] = []
        if not os.path.isdir(self.base_scan_dir):
            return scans
        for f in os.listdir(self.base_scan_dir):
            path = os.path.join(self.base_scan_dir, f)
            if os.path.isdir(path):
                images_folder = os.path.join(path, IMG_DIR_NAME)
                if os.path.isdir(images_folder):
                    number_of_images = len(os.listdir(images_folder))
                else:
                    number_of_images = 0
                scans.append(
                    ScanInfo(
                        name=f,
                        created=os.path.getctime(path),
                        modified=os.path.getmtime(path),
                        number_of_images=number_of_images,
                    )
                )
        return scans

    @fastapi_endpoint(
        "get",
        "scans/{scan_name}/{file}",
        responses={
            200: {
                "description": "Successfully downloading file",
                "content": {"*/*": {}},
            },
            403: {"description": "Filename not permitted"},
            404: {"description": "File not found"},
        },
    )
    def get_scan_file(self, scan_name: str, file: str) -> FileResponse:
        """Retrieve a file from a scan.

        This endpoint allows files to be downloaded from a scan. For security
        reasons, there is a list of allowable filenames, and paths with additional
        slashes are not permitted.
        """
        if file not in DOWNLOADABLE_SCAN_FILES:
            raise HTTPException(
                403, f"You may only download files named {DOWNLOADABLE_SCAN_FILES}"
            )
        path = os.path.join(self.base_scan_dir, scan_name, file)
        if not os.path.isfile(path):
            raise HTTPException(404, "File not found")
        return FileResponse(path)

    @fastapi_endpoint(
        "delete",
        "scans/{scan_name}",
        responses={
            200: {"description": "Successfully deleted scan"},
            404: {"description": "Scan not found"},
        },
    )
    def delete_scan(self, scan_name: str) -> None:
        """Delete all files from a scan.

        This endpoint allows scans to be deleted from disk.
        """
        path = os.path.join(self.base_scan_dir, scan_name)
        if not os.path.isdir(path):
            print(f"can't find {path}")
            raise HTTPException(404, "Scan not found")
        shutil.rmtree(path)

    @fastapi_endpoint(
        "delete",
        "scans",
    )
    def delete_all_scans(self) -> None:
        """Delete all the scans on the microscope

        **This will irreversibly remove all smart scan data from the
        microscope!**
        Use with extreme caution.
        """
        for scan in self.scans:
            self.delete_scan(scan.name)

    @property
    def latest_preview_stitch_path(self):
        """Return the path of the latest preview stitched image

        If the image cannot be found (because there is no latest
        scan, or because the latest scan has no preview stitch) then
        raise FileNotFoundError
        """
        if not self.latest_scan_name:
            raise FileNotFoundError("No latest scan found")

        images_dir = self.images_dir_for_scan(self.latest_scan_name)
        stitch_path = os.path.join(images_dir, "stitched_from_stage.jpg")
        if not os.path.isfile(stitch_path):
            raise FileNotFoundError("Latest scan has no preview stitch")
        return stitch_path

    @thing_property
    def latest_preview_stitch_time(self) -> Optional[datetime]:
        """The modification time of the latest preview image

        This will return `null` if there is no preview image to return.
        """
        try:
            return os.path.getmtime(self.latest_preview_stitch_path)
        except FileNotFoundError:
            return None

    @fastapi_endpoint(
        "get",
        "latest_preview_stitch.jpg",
        responses={
            200: {
                "description": "A preview-quality stitched image",
                "content": {"image/jpeg": {}},
            },
            404: {"description": "File not found"},
        },
    )
    def get_latest_preview(self) -> FileResponse:
        """Retrieve the latest preview image."""
        try:
            return FileResponse(self.latest_preview_stitch_path)
        except FileNotFoundError:
            raise HTTPException(404, "File not found")

    @_scan_running
    def _preview_stitch_start(self) -> None:
        """Start stitching a preview of the scan in a background subprocess


        This uses popen and returns immediately

        - self._preview_stitch_popen holds the popen for polling
        - self._preview_stitch_popen_lock is a lock aquired while interacting
              with Popen
        """
        if self._preview_stitch_running():
            raise RuntimeError("Only one subprocess is allowed at a time")
        with self._preview_stitch_popen_lock:
            self._preview_stitch_popen = Popen(
                [
                    self._stitching_script,
                    "--stitching_mode",
                    "only_stage_stitch",
                    self._ongoing_scan_images_dir,
                ]
            )

    @_scan_running
    def _preview_stitch_running(self) -> bool:
        """Whether there is a preview stitch running in a subprocess"""
        with self._preview_stitch_popen_lock:
            if self._preview_stitch_popen is None:
                return False
            if self._preview_stitch_popen.poll() is None:
                return True
            return False

    @_scan_running
    def _preview_stitch_wait(self):
        if self._preview_stitch_running():
            with self._preview_stitch_popen_lock:
                self._preview_stitch_popen.wait()

    @_scan_running
    def _correlate_start(self, overlap: float = 0.1) -> None:
        """Start stitching a preview of the scan in a subprocess"""
        if self._correlate_running():
            raise RuntimeError("Only one subprocess is allowed at a time")
        with self._correlate_popen_lock:
            self._correlate_popen = Popen(
                [
                    self._stitching_script,
                    "--stitching_mode",
                    "only_correlate",
                    "--minimum_overlap",
                    f"{round(overlap * 0.9, 2)}",
                    self._ongoing_scan_images_dir,
                ]
            )

    @_scan_running
    def _correlate_running(self) -> bool:
        """Whether there is a preview stitch running in a subprocess"""
        with self._correlate_popen_lock:
            if self._correlate_popen is None:
                return False
            if self._correlate_popen.poll() is None:
                return True
            return False

    @_scan_running
    def _correlate_wait(self):
        if self._correlate_running():
            with self._correlate_popen_lock:
                self._correlate_popen.wait()

    def run_subprocess(
        self,
        logger: InvocationLogger,
        cmd: list[str],
    ) -> CompletedProcess:
        """Run a  subprocess and log any output"""
        logger.info(f"Running command in subprocess: `{' '.join(cmd)}`")

        p = Popen(cmd, stdout=PIPE, stderr=STDOUT, bufsize=1, universal_newlines=True)
        os.set_blocking(p.stdout.fileno(), False)
        logger.info(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
        while p.poll() is None:
            try:
                output = p.stdout.readline()
                if output != "" and output is not None:
                    logger.info(output)
            except:
                pass

        for line in p.stdout:
            try:
                output = p.stdout.readline()
                if output != "" and output is not None:
                    logger.info(output)
            except:
                pass

        logger.info("Stitching complete")
        return p

    @thing_action
    def stitch_scan(
        self,
        logger: InvocationLogger,
        scan_name: str,
        overlap: float = 0.0,
    ) -> None:
        """Generate a stitched image based on stage position metadata

        Note that as this is a thing_action it needs the logger passed as
        a variable if called from another thing action
        """
        images_folder = self.images_dir_for_scan(scan_name=scan_name)

        if self.stitch_tiff:
            tiff_arg = "--stitch_tiff"
        else:
            tiff_arg = "--no-stitch_tiff"

        if overlap == 0.0:
            try:
                with open(os.path.join(images_folder, "scan_inputs.json")) as data_file:
                    data_loaded = json.load(data_file)
                    logger.info(data_loaded)
                overlap = data_loaded["overlap"]
            except:
                overlap = 0.1
        self.run_subprocess(
            logger,
            [
                self._stitching_script,
                "--stitching_mode",
                "all",
                f"{tiff_arg}",
                "--minimum_overlap",
                f"{round(overlap * 0.9, 2)}",
                images_folder,
            ],
        )

    @thing_action
    def create_zip_of_scan(
        self,
        logger: InvocationLogger,
        scan_name: str,
        download_zip=True,
    ) -> ZipBlob:
        """Generate a zip file that can be downloaded, with all the scan files in it.

        Note that as this is a thing_action it needs the logger passed as
        a variable if called from another thing action
        """
        images_folder = self.images_dir_for_scan(scan_name=scan_name)
        scan_folder = self.dir_for_scan(scan_name=scan_name)

        if not os.path.isdir(images_folder):
            raise FileNotFoundError(
                f"Tried to make a zip archive of {images_folder} but it does not exist."
            )

        zip_fname = os.path.join(scan_folder, "images.zip")

        # Create an empty zip file - we don't want to autofill it with files,
        # as some of them should only be added at the end (as we can't overwrite)
        # them once they change
        if not os.path.isfile(zip_fname):
            with zipfile.ZipFile(zip_fname, mode="w") as scan_zip:
                pass

        # get a list of files in the existing zip
        current_zip = self.get_files_in_zip(zip_fname)

        # get a list of files in the folder we're zipping

        files = glob.glob(scan_folder + "/**/*", recursive=True)
        files = [os.path.relpath(file, scan_folder) for file in files]

        # This is a list of file names that are updated as the scan goes,
        # and should only be zipped at the end of the scan - otherwise they'll
        # be appended on every loop as we can't overwrite files in the zip
        files_to_delay = [
            "TileConfiguration",
            "tiling_cache",
            "stitched.jp",
            "stitched_from",
            "stitched.om",
        ]
        tiff_name = ""

        with zipfile.ZipFile(zip_fname, mode="a") as scan_zip:
            for file in files:
                if "stitched.jp" in file:
                    stitch_name = os.path.split(file)[1]
                if ".ome.tiff" in file:
                    tiff_name = os.path.split(file)[1]
                if any(banned_name in file for banned_name in files_to_delay):
                    pass
                elif file in current_zip:
                    pass
                elif ".zip" in file or "raw" in file:
                    pass
                else:
                    logger.info(f"appending {file} to zip")
                    scan_zip.write(os.path.join(scan_folder, file), arcname=file)

        # Promote key files to the top level of the zip only at the end of the scan (when downloading)
        # and finally zip some of the final files
        # TODO: if you download multiple times, you get duplicate files - is this a problem?
        if download_zip:
            with zipfile.ZipFile(zip_fname, mode="a") as scan_zip:
                for fname in ["stitched_from_stage.jpg", stitch_name, tiff_name]:
                    fpath = os.path.join(images_folder, fname)
                    if os.path.exists(fpath):
                        logger.info(f"copying {fpath} to upper level")
                        scan_zip.write(fpath, arcname=fname)
                for file in files:
                    if any(banned_name in file for banned_name in files_to_delay):
                        logger.info(f"we are finally adding {file} into zip")
                        scan_zip.write(os.path.join(scan_folder, file), arcname=file)
            logger.info("about to download zip")
            return ZipBlob.from_file(zip_fname)

    @thing_action
    def get_files_in_zip(self, zip_path):
        """List the relative paths of all files and folders in the zip folder specified"""
        scan_zip = zipfile.ZipFile(zip_path)
        return [os.path.normpath(i) for i in scan_zip.namelist()]


class CaptureError(RuntimeError):
    """An error trying to capture from Picamera"""
