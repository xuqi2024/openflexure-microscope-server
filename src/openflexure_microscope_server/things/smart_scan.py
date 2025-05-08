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
import glob
import json
import re

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
from openflexure_microscope_server import scan_planners

CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")
BackgroundDep = direct_thing_client_dependency(
    BackgroundDetectThing, "/background_detect/"
)

IMAGE_REGEX = re.compile(r"-?[0-9]+_-?[0-9]+\.jpeg$")


class NotEnoughFreeSpaceError(IOError):
    pass


def ensure_free_disk_space(path: str, min_space: int = 500000000) -> None:
    """
    Raise an exception if we are running out of disk space

    Args:
       path =  path to a location on the disk you want to check
       min_space [int] = the minimum space required in bytes
           default = 500,000,000 (500MiB)

    Raises:
        NotEnoughFreeSpaceError if the remaining storage is below min_space
    """
    du = shutil.disk_usage(path)
    if du.free < min_space:
        raise NotEnoughFreeSpaceError(
            "There is not enough free disk space to continue. "
            f"(Required: {min_space}, {du})."
        )


class ScanInfo(BaseModel):
    """Summary information about a scan folder"""

    """Summary information about a scan folder"""

    name: str
    created: datetime
    modified: datetime
    number_of_images: int


DOWNLOADABLE_SCAN_FILES = (
    "images.zip",
    "stitched_thumbnail.jpg",
)

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
        self._capture_thread: Optional[ErrorCapturingThread] = None
        self._scan_images_taken: Optional[int] = None
        # TODO Scan data is a dict during refactoring, should become a dataclass
        self._scan_data: Optional[dict] = None

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
        background_detect Thing) or reaches the "max_range" measured in steps.
        """

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
        self._capture_thread = None
        self._scan_images_taken = 0

        # Don't set self._scan_data dictionary. This is done at the start of _run_scan

        try:
            self._check_background_and_csm_set()
            self._ongoing_scan_name = self._get_unique_scan_name_and_dir(scan_name)
            self.create_zip_of_scan(scan_name=self._ongoing_scan_name)
            self._autofocus.looping_autofocus(dz=self.autofocus_dz, start="centre")
            # record starting position so we can return there
            self._starting_position = self._stage.position
            self._run_scan()
        except Exception as e:
            # If _scan_data is set then scan started
            if self._scan_data is not None:
                self._return_to_starting_position()
                if not isinstance(e, NotEnoughFreeSpaceError):
                    # Don't stich if drive is full (already logged)
                    self._perform_final_stitch()
            # Error must be raised so UI gives correct output
            raise e
        finally:
            # However the scan finishes, unset all variables and release lock
            self._cancel = None
            self._scan_logger = None
            self._autofocus = None
            self._stage = None
            self._cam = None
            self._metadata_getter = None
            self._csm = None
            self._background_detect = None
            self._capture_thread = None
            self._ongoing_scan_name = None
            self._scan_images_taken = None
            self._scan_data = None
            self._scan_lock.release()

    def promote_stitch_files(
        self,
        logger,
    ):
        """Copy the stitched image from the scan images folder to the top level"""

        # Search the scan images dir for a file ending in '_stitched.jpg
        stitched_image_path = glob.glob(
            os.path.join(self._ongoing_scan_images_dir, "*_stitched.jpg")
        )

        if len(stitched_image_path) == 0:
            logger.warning("Could't find a stitched image to copy")
        else:
            for stitched_image in stitched_image_path:
                stitch_name = os.path.basename(stitched_image)

                shutil.copy(
                    stitched_image,
                    os.path.join(
                        self.dir_for_scan(self._ongoing_scan_name), stitch_name
                    ),
                )

    @_scan_running
    def _check_background_and_csm_set(self):
        """Before starting a scan, check that background and camera-stage-mapping are set

        Raise error if:
          - background is to be skipped but is not set
          - camera stage mapping is not set

        Raise warning if not using background detect that scan will go on until max steps reached
        """
        if self._csm.image_resolution is None:
            raise RuntimeError(
                "Camera-stage mapping is not calibrated. This is required before "
                "scans can be carried out."
            )

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
        """For the ongoing scan, this returns the scan directory"""
        if not self._ongoing_scan_name:
            raise RuntimeError("Cannot get ongoing scan name while no scan is running")
        return self.dir_for_scan(self._ongoing_scan_name)

    @property
    @_scan_running
    def _ongoing_scan_images_dir(self):
        """For the ongoing scan, this returns the image directory"""
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
                # Save the scan name as the latest scan (this persists as a
                # property after the scan finishes)
                self._latest_scan_name = trial_unique_scan_name
                # Create images directory and
                os.mkdir(self.images_dir_for_scan(trial_unique_scan_name))
                # Return the scan name
                return trial_unique_scan_name
        raise FileExistsError("Could not create a new scan folder: all names in use!")

    @_scan_running
    def _move_to_next_point(
        self, next_point: tuple[int, int], z_estimate: Optional[int] = None
    ) -> tuple[int, int, int]:
        """Moves the stage to the next poistion. If no z_estimate is given then
        the current stage position is used. Must move to the estimated focused position
        (although moving below would be marginally faster) because background detect is
        most reliable at the focused position.

        Returns the (x,y,z) with the chosen z_estimate
        """

        if z_estimate is None:
            z_estimate = self._stage.position["z"]

        self._scan_logger.info(f"Moving to {next_point}")
        self._stage.move_absolute(
            x=next_point[0],
            y=next_point[1],
            z=z_estimate,
        )

        return (next_point[0], next_point[1], z_estimate)

    @_scan_running
    def _take_test_image_to_calc_displacement(self, overlap):
        """
        Take a test image and use camera stage mapping to calculate x and y displacement

        Return (dx, dy) - the x and y displacments in steps
        """
        test_jpg = self._cam.grab_jpeg()
        test_image = np.array(Image.open(test_jpg.open()))

        test_image_res = list(test_image.shape[:2])
        csm_image_res = [int(i) for i in self._csm.image_resolution]

        if test_image_res != csm_image_res:
            raise RuntimeError(
                "Cannot start scan as it is set up to capture with a resolution that "
                "has not been mapped.\n"
                f"Scan resolution: {test_image_res}\n"
                f"camera-stage-mapping resolution {csm_image_res}."
            )

        # get displacement matrix. note it is for (y, x) not (x, y) coordinates
        csm_disp_matrix = self._csm.image_to_stage_displacement_matrix

        # Calculate displacements in image coordinates
        dx_img = test_image.shape[1] * (1 - overlap)
        dy_img = test_image.shape[0] * (1 - overlap)

        # Calculate displacements in steps as vectors using a dot product with the matrix
        dx_vec = np.dot(np.array([0, dx_img]), csm_disp_matrix)
        dy_vec = np.dot(np.array([dy_img, 0]), csm_disp_matrix)

        # Assume no rotation or skew and take only the aligned axis of vector.
        # Coerce to positive integer
        dx = int(np.abs(dx_vec[0]))
        dy = int(np.abs(dy_vec[1]))

        return dx, dy

    @_scan_running
    def _set_scan_data(self):
        """
        This sets the self._scan_data dictionary. This needs to become a
        dataclass.
        """
        overlap = self.overlap
        dx, dy = self._take_test_image_to_calc_displacement(overlap)
        self._scan_logger.info(
            f"Based on an overlap of {overlap}, we will make steps of {dx}, {dy}"
        )

        autofocus_dz = self.autofocus_dz
        if autofocus_dz == 0:
            self._scan_logger.info("Running scan without autofocus")
        elif autofocus_dz <= 200:
            self._scan_logger.warning(
                f"Your autofocus range is {autofocus_dz} steps, which is too short to "
                "attempt to focus. Running without autofocus"
            )
            autofocus_dz = 0

        # Fix scan parameters in case UI is updated during scan.
        self._scan_data = {
            "scan_name": self._ongoing_scan_name,
            "overlap": overlap,
            "max_dist": self.max_range,
            "dx": dx,
            "dy": dy,
            "autofocus_dz": autofocus_dz,
            "autofocus_on": bool(autofocus_dz),
            "start_time": time.strftime("%H_%M_%S-%d_%m_%Y"),
            "skip_background": self.skip_background,
            "stitch_automatically": self.stitch_automatically,
        }

    @_scan_running
    def _save_scan_inputs_json(self):
        """
        Save scan inputs as a JSON file in the scan folder, to allow
        the user to review the settings used in the scan
        """
        # This should be a method of the scan_data dataclass

        data = {
            "scan_name": self._ongoing_scan_name,
            "overlap": self._scan_data["overlap"],
            "autofocus range": self._scan_data["autofocus_dz"],
            "dx": self._scan_data["dx"],
            "dy": self._scan_data["dy"],
            "start time": self._scan_data["start_time"],
            "skipping background": self._scan_data["skip_background"],
        }

        scan_inputs_fname = os.path.join(
            self._ongoing_scan_images_dir, "scan_inputs.json"
        )
        with open(scan_inputs_fname, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @_scan_running
    def _manage_stitching_threads(self):
        """
        Manage the stitching threads, starting them if needed and not already running.
        """

        # Assume 4 images means at least one offset in x and y, making the stitching
        # well constrained.
        if self._scan_images_taken > 3:
            if not self._preview_stitch_running():
                self._preview_stitch_start(overlap=self._scan_data["overlap"])

    @_scan_running
    def _run_scan(self):
        """
        Prepare and run the main scan, handling the threads performing
        stitching. Uses the result (or exception) from the scanning to
        determine whether the scan should be stitched and the microscope
        should return to the starting x,y,z position
        """

        # Used to check if finally was reached via exeption (except
        # cancel by user)
        scan_successful = True

        try:
            self._set_scan_data()
            self._save_scan_inputs_json()
            if self._scan_images_taken != 0:
                msg = "_scan_images_taken should be zero before starting scanning"
                raise RuntimeError(msg)

            # This is the main loop of the scan!
            self._main_scan_loop()

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
            if self._capture_thread:
                # If the capture thread had an error, we capture it here
                try:
                    self._capture_thread.join()
                except Exception as e:
                    # If the scan has already ended due to an exception,
                    # ignore any exceptions. If it appeared to be successful,
                    # log the error.
                    if scan_successful:
                        self._scan_logger.error(
                            "The scan appears to have started successfully, however "
                            f"the final capture raised the following error: {e}."
                            "Attempting to stitch and archive images.",
                            exc_info=e,
                        )

        # This is what happens if the scan completes successfully or the
        # user cancels it.
        self._return_to_starting_position()
        self._perform_final_stitch()

    @_scan_running
    def _main_scan_loop(self):
        """
        The loop to run through during a scan, until no more scan x,y positions
        are remaining.
        """

        # The initial plan for the scan should be a single x,y position. All future
        # moves will be planned around this point. In future, route planner could
        # have multiple starting positions, each of which will be visited before the
        # scan can end.
        planner_settings = {
            "dx": self._scan_data["dx"],
            "dy": self._scan_data["dy"],
            "max_dist": self._scan_data["max_dist"],
        }
        route_planner = scan_planners.SmartSpiral(
            intial_position=(self._stage.position["x"], self._stage.position["y"]),
            planner_settings=planner_settings,
        )

        # The loop tests if the scan should continue, moves to the next position,
        # decides whether to capture an image, autofocuses if necessary,
        # captures an image if necessary, updates the scan path and future path,
        # and updates the zip file with new images.
        while not route_planner.scan_complete:
            ensure_free_disk_space(self._ongoing_scan_dir)
            self._manage_stitching_threads()

            next_pos_xy, z_est = route_planner.get_next_location_and_z_estimate()
            new_pos_xyz = self._move_to_next_point(next_pos_xy, z_est)
            current_pos_xyz = (
                new_pos_xyz[0],
                new_pos_xyz[1],
                self._stage.position["z"],
            )

            capture_image = True
            # If skipping background, take an image to check if current field of view is background
            if self._scan_data["skip_background"]:
                capture_image = self._background_detect.image_is_sample()

            if not capture_image:
                route_planner.mark_location_visited(
                    new_pos_xyz, imaged=False, focused=False
                )
                # Background fraction is actually a percentage
                back_perc = round(self._background_detect.background_fraction(), 0)
                msg = f"Skipping {new_pos_xyz} as it is {back_perc}% background."
                self._scan_logger.info(msg)
                continue

            focused = False
            if self._scan_data["autofocus_on"]:
                self._autofocus.looping_autofocus(
                    dz=self._scan_data["autofocus_dz"], start="centre"
                )
                current_pos_xyz = (
                    new_pos_xyz[0],
                    new_pos_xyz[1],
                    self._stage.position["z"],
                )
                # Without a test for autofocus success, assume it worked
                focused = True

            route_planner.mark_location_visited(
                current_pos_xyz, imaged=True, focused=focused
            )

            site_folder = os.path.join(
                self._ongoing_scan_images_dir,
                "stacks",
                f"{new_pos_xyz[0]}_{new_pos_xyz[1]}",
            )
            os.makedirs(site_folder, exist_ok=True)
            self._autofocus.run_z_stack(
                images_dir=self._ongoing_scan_images_dir,
                stack_dir=site_folder,
            )

            # increment capure counter as thread has completed
            self._scan_images_taken += 1
            # Add it to the incremental zip
            self.update_zip(
                scan_name=self._ongoing_scan_name,
            )

    @_scan_running
    def _return_to_starting_position(self):
        """Return to the initial scan position, if set"""
        self._scan_logger.info("Returning to starting position.")
        if self._starting_position is not None:
            self._stage.move_absolute(
                **self._starting_position, block_cancellation=True
            )

    @_scan_running
    def _perform_final_stitch(self):
        """Update the scan zip and perform final stitch of the data"""

        if self._scan_images_taken <= 3:
            self._scan_logger.info("Not performing a stitch as 3 or fewer images taken")
            return

        self.update_zip(
            scan_name=self._ongoing_scan_name,
            final_version=False,
        )
        self._scan_logger.info("Waiting for background processes to finish...")

        self._preview_stitch_wait()
        try:
            if self._scan_data["stitch_automatically"]:
                self._scan_logger.info("Stitching final image (may take some time)...")
                self.stitch_scan(
                    logger=self._scan_logger,
                    scan_name=self._ongoing_scan_name,
                    overlap=self._scan_data["overlap"],
                )
                self.promote_stitch_files(self._scan_logger)
        except SubprocessError as e:
            self._scan_logger.error(f"Stitching failed: {e}", exc_info=e)

    @fastapi_endpoint(
        "get",
        "scans/stitched_thumbnail.jpg",
        responses={
            200: {
                "description": "A thumbnail-quality stitched image",
                "content": {"image/jpeg": {}},
            },
            404: {"description": "File not found"},
        },
    )
    def get_scan_thumbnail(self, scan_name: str) -> FileResponse:
        """Retrieve a file from a scan.

        This endpoint allows files to be downloaded from a scan.
        """
        path = os.path.join(
            self.images_dir_for_scan(scan_name), "stitched_thumbnail.jpg"
        )
        if not os.path.isfile(path):
            raise HTTPException(404, "File not found")
        return FileResponse(path)

    @thing_property
    def max_range(self) -> int:
        """The maximum distance from the centre of the scan before we break in steps"""
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
        """The z distance to perform an autofocus in steps"""
        return self.thing_settings.get("autofocus_dz", 1000)

    @autofocus_dz.setter
    def autofocus_dz(self, value: int) -> None:
        self.thing_settings["autofocus_dz"] = value

    @thing_property
    def overlap(self) -> float:
        """The fraction (0-1) that adjacent images should overlap in x or y"""
        return self.thing_settings.get("overlap", 0.45)

    @overlap.setter
    def overlap(self, value: float) -> None:
        self.thing_settings["overlap"] = value

    @thing_property
    def stitch_automatically(self) -> bool:
        """Whether to run a final stitch at the end of the scan (assuming scan success)"""
        return self.thing_settings.get("stitch_automatically", True)

    @stitch_automatically.setter
    def stitch_automatically(self, value: bool) -> None:
        self.thing_settings["stitch_automatically"] = value

    @thing_property
    def scans(self) -> list[ScanInfo]:
        """All the available scans

        Each scan has a name (which can be used to access it), along with
        its modified and created times (according to the filesystem) and
        the number of items in the `images` folder. Note that image count
        uses a regular expression, and changes to the naming scheme will
        break it.
        """
        scans: list[ScanInfo] = []
        if not os.path.isdir(self.base_scan_dir):
            return scans
        for f in os.listdir(self.base_scan_dir):
            path = os.path.join(self.base_scan_dir, f)
            if os.path.isdir(path):
                images_folder = os.path.join(path, IMG_DIR_NAME)
                if os.path.isdir(images_folder):
                    folder_contents = os.listdir(images_folder)
                    scan_images = [x for x in folder_contents if IMAGE_REGEX.search(x)]
                    number_of_images = len(scan_images)
                else:
                    number_of_images = 0
                modified = max(os.stat(root).st_mtime for root, _, _ in os.walk(path))
                # If number of images is 0, should the scan be appended or ignored?
                # When deleting images, empty scans should be deleted. When displaying
                # scans in the GUI or choosing a new scan name, should be ignored

                # A function to delete empty scan folders from the disk achieves all of this
                scans.append(
                    ScanInfo(
                        name=f,
                        created=os.path.getctime(path),
                        modified=modified,
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

        **This will irreversibly remove all scanned data from the
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
    def _preview_stitch_start(self, overlap: float) -> None:
        """Start stitching a preview of the scan in a background subprocess


        This uses popen and returns immediately

        - self._preview_stitch_popen holds the popen for polling
        - self._preview_stitch_popen_lock is a lock aquired while interacting
              with Popen
        """
        # Set minimum overlap to 90% of the scan overlap to catch only images directly adjacent,
        # not images with overlapping corners.
        min_overlap = round(overlap * 0.9, 2)
        if self._preview_stitch_running():
            raise RuntimeError("Only one subprocess is allowed at a time")
        with self._preview_stitch_popen_lock:
            self._preview_stitch_popen = Popen(
                [
                    self._stitching_script,
                    "--stitching_mode",
                    "only_stage_stitch",
                    "--minimum_overlap",
                    f"{min_overlap}",
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
        """
        Wait for an ongoing preview stitch to return
        """
        if self._preview_stitch_running():
            with self._preview_stitch_popen_lock:
                self._preview_stitch_popen.wait()

    def run_subprocess(
        self,
        logger: InvocationLogger,
        cmd: list[str],
    ) -> CompletedProcess:
        """
        Run a  subprocess and log any output

        Raises:
            ChildProcessError if exit code is not zero
        """
        logger.info(f"Running command in subprocess: `{' '.join(cmd)}`")

        def log_buffer(buffer):
            """A short internal function to read everything in the buffer to
            a multiline string and log"""
            lines = []
            while line := buffer.readline():
                lines.append(line)
            if lines:
                logger.info("".join(lines))

        # Run the command piping stdout into the process for reading and
        # forwarding the stdrerr to stdout
        process = Popen(
            cmd, stdout=PIPE, stderr=STDOUT, bufsize=1, universal_newlines=True
        )
        # Stop opening pipe blocking writing to it
        os.set_blocking(process.stdout.fileno(), False)
        logger.info(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))

        # Poll returns None while running, will return the error code when finnished
        while process.poll() is None:
            log_buffer(process.stdout)
            # Once buffer is clear sleep for 0.2s before trying again.
            time.sleep(0.2)

        # Print everything in the buffer when program finishes
        log_buffer(process.stdout)

        if process.poll() == 0:
            logger.info("Stitching complete")
        else:
            raise ChildProcessError(f"Subprocess {cmd[0]} exited with an error.")

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
        json_fname = "scan_inputs.json"
        images_folder = self.images_dir_for_scan(scan_name=scan_name)
        json_fpath = os.path.join(images_folder, json_fname)

        if self.stitch_tiff:
            tiff_arg = "--stitch_tiff"
        else:
            tiff_arg = "--no-stitch_tiff"

        if overlap == 0.0:
            try:
                with open(json_fpath, "r", encoding="utf-8") as data_file:
                    data_loaded = json.load(data_file)
                    logger.info(data_loaded)
                overlap = data_loaded["overlap"]
            except (json.decoder.JSONDecodeError, FileNotFoundError, TypeError):
                # As there is no schema or pydantic model this should handle
                # the file not being there, it not being json in the file,
                # or the imported data not being indexable
                logger.warning(
                    f"Couldn't read scan data, is {json_fname} missing or corrupt? "
                    "Attempting stitch with overlap value of 0.1"
                )
                overlap = 0.1
            except KeyError:
                logger.warning(
                    "Value for overlap not found in scan data. "
                    "Attempting stitch with overlap value of 0.1"
                )
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
        scan_name: str,
    ) -> None:
        """Generate an empty zip file for the current scan"""
        images_folder = self.images_dir_for_scan(scan_name=scan_name)
        scan_folder = self.dir_for_scan(scan_name=scan_name)

        if not os.path.isdir(images_folder):
            raise FileNotFoundError(
                f"Tried to make a zip archive of {images_folder} but it does not exist."
            )

        zip_fname = os.path.join(scan_folder, "images.zip")

        # Create an empty zip file
        if not os.path.isfile(zip_fname):
            with zipfile.ZipFile(zip_fname, mode="w"):
                pass

    def update_zip(
        self,
        scan_name: str,
        final_version: bool = False,
    ) -> None:
        """Update the zip file with any images added to the folder since the last run,
        except for files containing 'files_to_delay', which are files to only include
        once the scan is finished or the user wants to download the zip
        """
        scan_folder = self.dir_for_scan(scan_name=scan_name)

        zip_fname = os.path.join(scan_folder, "images.zip")

        # get a list of files in the existing zip
        current_zip = self.get_files_in_zip(zip_fname)

        # get a list of files in the folder we're zipping

        files = glob.glob(scan_folder + "/**/*", recursive=True)
        files = [os.path.relpath(file, scan_folder) for file in files]

        # This is a list of file names that are updated as the scan goes,
        # and should only be zipped at the end of the scan - otherwise they'll
        # be appended on every loop as we can't overwrite files in the zip

        # More elegant ways would be to only zip the images matching the global regex,
        # which will all be images, then append other files at the end.
        # Alternatively, use "output_dir" in stitching to separate stitching image files
        files_to_delay = [
            "TileConfiguration",
            "tiling_cache",
            "stitched.jp",
            "stitched_from",
            "stitched.om",
            "stitching_correlations",
        ]

        with zipfile.ZipFile(zip_fname, mode="a") as scan_zip:
            for file in files:
                if any(skipped_name in file for skipped_name in files_to_delay):
                    pass
                elif file in current_zip:
                    pass
                elif ".zip" in file:
                    pass
                else:
                    scan_zip.write(os.path.join(scan_folder, file), arcname=file)

        # Finally, zip the files skipped previously
        if final_version:
            with zipfile.ZipFile(zip_fname, mode="a") as scan_zip:
                for file in files:
                    if any(delayed_name in file for delayed_name in files_to_delay):
                        scan_zip.write(os.path.join(scan_folder, file), arcname=file)

    @thing_action
    def download_zip(
        self,
        scan_name: str,
    ):
        """Update the zip to include the files left until the end, then return the
        zip file as a Blob"""
        self.update_zip(
            scan_name=scan_name,
            final_version=True,
        )

        scan_folder = self.dir_for_scan(scan_name=scan_name)

        zip_fname = os.path.join(scan_folder, "images.zip")
        return ZipBlob.from_file(zip_fname)

    def get_files_in_zip(self, zip_path):
        """List the relative paths of all files and folders in the zip folder specified"""
        scan_zip = zipfile.ZipFile(zip_path)
        return [os.path.normpath(i) for i in scan_zip.namelist()]
