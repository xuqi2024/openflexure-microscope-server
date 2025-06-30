from typing import Optional, Mapping
import threading
import os
import time
import json
from datetime import datetime
from subprocess import CompletedProcess, Popen, PIPE, SubprocessError, STDOUT

from fastapi import HTTPException
from fastapi.responses import FileResponse
import numpy as np
from PIL import Image

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

from openflexure_microscope_server.utilities import ErrorCapturingThread
from openflexure_microscope_server import scan_directories
from openflexure_microscope_server import scan_planners

# Things
from .autofocus import AutofocusThing
from .camera_stage_mapping import CameraStageMapper
from .background_detect import BackgroundDetectThing
from .camera import CameraDependency as CamDep
from .stage import StageDependency as StageDep

CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")
BackgroundDep = direct_thing_client_dependency(
    BackgroundDetectThing, "/background_detect/"
)

JPEGBlob = blob_type("image/jpeg")
ZipBlob = blob_type("application/zip")

SCAN_DATA_FILENAME = "scan_data.json"
STITCHING_CMD = "openflexure-stitch"

STITCHING_RESOLUTION = (820, 616)


class ScanNotRunningError(RuntimeError):
    """Exception called when scan not running that requires a scan to be running"""


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
        raise ScanNotRunningError(
            "Calling a @scan_running method can only be done while a scan is running!"
        )

    return scan_running_wrapper


class SmartScanThing(Thing):
    def __init__(self, scans_folder):
        self._scan_dir_manager = scan_directories.ScanDirectoryManager(scans_folder)
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
        self._ongoing_scan: Optional[scan_directories.ScanDirectory] = None
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

        # Set _scan_data to None. This is needed just in case an exception is raised
        # before _run_scan (which sets the real data). As we check this in the `except`
        self._scan_data = None

        try:
            self._check_background_and_csm_set()
            self._ongoing_scan = self._scan_dir_manager.new_scan_dir(scan_name)
            self._latest_scan_name = self._ongoing_scan.name
            self._autofocus.looping_autofocus(dz=self.autofocus_dz, start="centre")
            # record starting position so we can return there
            self._starting_position = self._stage.position
            self._run_scan()
        except Exception as e:
            # If _scan_data is set then scan started
            if self._scan_data is not None:
                self._return_to_starting_position()
                if not isinstance(e, scan_directories.NotEnoughFreeSpaceError):
                    # Don't stitch if drive is full (already logged)
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
            self._ongoing_scan = None
            self._scan_images_taken = None
            self._scan_data = None
            self._scan_lock.release()

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

    @thing_property
    def latest_scan_name(self) -> Optional[str]:
        """The name of the last scan to be started."""
        return self._latest_scan_name

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
    def _calc_displacement_from_test_image(self, overlap: int) -> tuple[int, int]:
        """
        Take a test image and use camera stage mapping to calculate x and y displacement

        :param overlap: The desired overlap as a fraction of the image. i.e. 0.5 means
        that each image should overlap its nearest neighbour by 50%.

        Return (dx, dy) - the x and y displacments in steps
        """
        test_jpg = self._cam.grab_jpeg()
        test_image = np.array(Image.open(test_jpg.open()))

        test_image_res = list(test_image.shape)
        csm_image_res = [int(i) for i in self._csm.image_resolution]

        # If current stream width is different to csm calibration width,
        # perform the conversion here
        res_ratio = csm_image_res[0] / test_image_res[0]

        # get displacement matrix. note it is for (y, x) not (x, y) coordinates
        csm_disp_matrix = np.array(self._csm.image_to_stage_displacement_matrix)
        csm_disp_matrix *= res_ratio

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
        dx, dy = self._calc_displacement_from_test_image(overlap)
        stitch_resize = STITCHING_RESOLUTION[0] / self.save_resolution[0]

        self._scan_logger.debug(
            f"Resizing images when stitching by a factor of {stitch_resize}"
        )

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
            "scan_name": self._ongoing_scan.name,
            "overlap": overlap,
            "max_dist": self.max_range,
            "dx": dx,
            "dy": dy,
            "autofocus_dz": autofocus_dz,
            "autofocus_on": bool(autofocus_dz),
            "start_time": time.strftime("%H_%M_%S-%d_%m_%Y"),
            "skip_background": self.skip_background,
            "stitch_automatically": self.stitch_automatically,
            "stitch_resize": stitch_resize,
            "save_resolution": self.save_resolution,
        }

    @_scan_running
    def _save_scan_inputs_json(self):
        """
        Save scan inputs as a JSON file in the scan folder, to allow
        the user to review the settings used in the scan
        """
        # Should this be a method of the scan_data dataclass?

        data = {
            "scan_name": self._ongoing_scan.name,
            "overlap": self._scan_data["overlap"],
            "autofocus range": self._scan_data["autofocus_dz"],
            "dx": self._scan_data["dx"],
            "dy": self._scan_data["dy"],
            "start time": self._scan_data["start_time"],
            "skipping background": self._scan_data["skip_background"],
            "capture resolution": self._scan_data["save_resolution"],
        }

        scan_inputs_fname = os.path.join(
            self._ongoing_scan.images_dir, SCAN_DATA_FILENAME
        )
        with open(scan_inputs_fname, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @_scan_running
    def _update_scan_data_json(self, scan_result: str):
        """
        Update scan data as a JSON file in the scan folder, with
        data only known at the end of the scan.

        Takes scan_result, a string that is either "success",
        "cancelled by user", or the error that ended the scan.
        """
        # Should this be a method of the scan_data dataclass?
        current_time = datetime.now().replace(microsecond=0)
        start_time = datetime.strptime(
            self._scan_data["start_time"], "%H_%M_%S-%d_%m_%Y"
        ).replace(microsecond=0)

        duration = current_time - start_time

        outputs = {
            "image_count": self._scan_images_taken,
            "duration": str(duration),
            "scan_result": scan_result,
        }

        scan_data_fname = os.path.join(
            self._ongoing_scan.images_dir, SCAN_DATA_FILENAME
        )

        with open(scan_data_fname, encoding="utf-8") as f:
            data = json.load(f)

        data.update(outputs)

        with open(scan_data_fname, "w", encoding="utf-8") as f:
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
            self._cam.start_streaming(main_resolution=(3280, 2464))
            self._set_scan_data()
            self._save_scan_inputs_json()
            if self._scan_images_taken != 0:
                msg = "_scan_images_taken should be zero before starting scanning"
                raise RuntimeError(msg)

            # This is the main loop of the scan!
            self._main_scan_loop()
            self._update_scan_data_json(scan_result="success")

        except InvocationCancelledError:
            scan_successful = False
            self._scan_logger.info("Stopping scan because it was cancelled.")
            self._update_scan_data_json(scan_result="cancelled by user")
        except scan_directories.NotEnoughFreeSpaceError as e:
            scan_successful = False
            self._update_scan_data_json(scan_result=str(e))
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
            # Start streaming in the default resolution again as soon as possible
            self._cam.start_streaming()
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

        # Remove any scan folders containing zero images
        self.purge_empty_scans(logger=self._scan_logger)

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
            self._scan_dir_manager.check_free_disk_space()
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

            focused, focused_height = self._autofocus.run_smart_stack(
                images_dir=self._ongoing_scan.images_dir,
                autofocus_dz=self._scan_data["autofocus_dz"],
                save_resolution=self._scan_data["save_resolution"],
            )

            current_pos_xyz = (new_pos_xyz[0], new_pos_xyz[1], focused_height)

            route_planner.mark_location_visited(
                current_pos_xyz, imaged=True, focused=focused
            )

            # increment capture counter as thread has completed
            self._scan_images_taken += 1
            # Add it to the incremental zip
            self._ongoing_scan.zip_files()

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

        self._ongoing_scan.zip_files()

        self._scan_logger.info("Waiting for background processes to finish...")

        self._preview_stitch_wait()
        try:
            if self._scan_data["stitch_automatically"]:
                self._scan_logger.info("Stitching final image (may take some time)...")
                self.stitch_scan(
                    logger=self._scan_logger,
                    scan_name=self._ongoing_scan.name,
                    stitch_resize=self._scan_data["stitch_resize"],
                    overlap=self._scan_data["overlap"],
                )
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
        preview_path = self._scan_dir_manager.get_file_from_img_dir(
            scan_name=scan_name, filename="stitched_thumbnail.jpg", check_exists=True
        )
        if preview_path is None:
            raise HTTPException(404, "File not found")
        return FileResponse(preview_path)

    @thing_property
    def save_resolution(self) -> tuple[int, int]:
        """A tuple of the image resolution to capture. Should be in a
        4:3 aspect ratio"""
        return self.thing_settings.get("save_resolution", ((1640, 1232)))

    @save_resolution.setter
    def save_resolution(self, value: tuple[int, int]) -> None:
        self.thing_settings["save_resolution"] = value

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
    def scans(self) -> list[scan_directories.ScanInfo]:
        """All the available scans

        Each scan has a name (which can be used to access it), along with
        its modified and created times (according to the filesystem) and
        the number of items in the `images` folder. Note that image count
        uses a regular expression, and changes to the naming scheme will
        break it.
        """
        return self._scan_dir_manager.all_scans_info()

    @fastapi_endpoint(
        "delete",
        "scans/{scan_name}",
        responses={
            200: {"description": "Successfully deleted scan"},
            400: {"description": "An error occurred while trying to delete scan"},
        },
    )
    def delete_scan(self, scan_name: str, logger: InvocationLogger) -> None:
        """Delete the folder for the specified scan.

        This endpoint allows scans to be deleted from disk.

        Takes the scan name to delete, and the Invocation Logger
        """
        if not self._scan_dir_manager.exists(scan_name):
            logger.warning(f"Cannot find a scan of name {scan_name}")
            raise HTTPException(400, "Scan not found")
        deleted_scan_success = self._delete_scan(scan_name, logger)
        if not deleted_scan_success:
            raise HTTPException(400, "Couldn't delete scan, check log for details")

    @fastapi_endpoint(
        "delete",
        "scans",
    )
    def delete_all_scans(self, logger: InvocationLogger) -> None:
        """Delete all the scans on the microscope

        **This will irreversibly remove all scanned data from the
        microscope!**
        Use with extreme caution.
        """
        for scan_name in self._scan_dir_manager.all_scans:
            self._delete_scan(scan_name, logger)

    @thing_action
    def purge_empty_scans(self, logger: InvocationLogger) -> None:
        """
        Delete all scan folders containing no images at the top level
        """

        # JSON is ignored as it's created before any images are captured
        for scan_info in self._scan_dir_manager.all_scans_info():
            if scan_info.number_of_images == 0:
                self._delete_scan(scan_info.name, logger)

    def _delete_scan(self, scan_name, logger: InvocationLogger) -> bool:
        """
        A wrapper around scan manager's delete_scan that logs to the invocation logger
        """
        try:
            self._scan_dir_manager.delete_scan(scan_name)
            return True
        except Exception as e:
            logger.warning(
                "Attempted to delete scan " + scan_name + ", which failed."
                " Server sent response" + str(e)
            )
            return False

    @property
    def latest_preview_stitch_path(self) -> Optional[str]:
        """The path of the latest preview stitched image, or None if not available"""

        if not self.latest_scan_name:
            return None

        return self._scan_dir_manager.get_file_from_img_dir(
            scan_name=self.latest_scan_name, filename="preview.jpg", check_exists=True
        )

    @thing_property
    def latest_preview_stitch_time(self) -> Optional[float]:
        """The modification time of the latest preview image, to allow live updating

        This will return None (`null` to JS) if there is no preview image to return.

        This is used for two reasons:
        1. If all caching was turned off this stitch would be sent over the network
           repeatedly
        2. If caching was is on, then the stitch will not update when needed.
        """
        if self.latest_preview_stitch_path is None:
            return None
        return os.path.getmtime(self.latest_preview_stitch_path)

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
        preview_path = self.latest_preview_stitch_path
        if preview_path is None:
            raise HTTPException(404, "File not found")
        return FileResponse(preview_path)

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
                    STITCHING_CMD,
                    "--stitching_mode",
                    "preview_stitch",
                    "--minimum_overlap",
                    f"{min_overlap}",
                    "--resize",
                    f"{self._scan_data['stitch_resize']}",
                    self._ongoing_scan.images_dir,
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
            the log"""
            while line := buffer.readline():
                logger.info(line)

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
        stitch_resize: Optional[float] = None,
        overlap: float = 0.0,
    ) -> None:
        """Generate a stitched image based on stage position metadata

        Note that as this is a thing_action it needs the logger passed as
        a variable if called from another thing action
        """
        json_fpath = self._scan_dir_manager.get_file_from_img_dir(
            scan_name=scan_name, filename=SCAN_DATA_FILENAME
        )

        if self.stitch_tiff:
            tiff_arg = "--stitch_tiff"
        else:
            tiff_arg = "--no-stitch_tiff"

        if overlap == 0.0:
            try:
                with open(json_fpath, "r", encoding="utf-8") as data_file:
                    data_loaded = json.load(data_file)
                overlap = data_loaded["overlap"]
            except (json.decoder.JSONDecodeError, FileNotFoundError, TypeError):
                # As there is no schema or pydantic model this should handle
                # the file not being there, it not being json in the file,
                # or the imported data not being indexable
                logger.warning(
                    f"Couldn't read scan data, is {SCAN_DATA_FILENAME} missing or corrupt? "
                    "Attempting stitch with overlap value of 0.1"
                )
                overlap = 0.1
            except KeyError:
                logger.warning(
                    "Value for overlap not found in scan data. "
                    "Attempting stitch with overlap value of 0.1"
                )
                overlap = 0.1

        if stitch_resize is None:
            try:
                with open(json_fpath, "r", encoding="utf-8") as data_file:
                    data_loaded = json.load(data_file)
                save_resolution = data_loaded["capture resolution"]
                stitch_resize = STITCHING_RESOLUTION[0] / save_resolution[0]
            except (json.decoder.JSONDecodeError, FileNotFoundError, TypeError):
                # As there is no schema or pydantic model this should handle
                # the file not being there, it not being json in the file,
                # or the imported data not being indexable
                logger.warning(
                    f"Couldn't read scan data, is {SCAN_DATA_FILENAME} missing or corrupt? "
                    "Attempting stitch with resize value of 0.5"
                )
                stitch_resize = 0.5
            except KeyError:
                logger.warning(
                    "Value for capture resolution not found in scan data. "
                    "Attempting stitch with resize value of 0.5"
                )
                stitch_resize = 0.5

        self.run_subprocess(
            logger,
            [
                STITCHING_CMD,
                "--stitching_mode",
                "all",
                f"{tiff_arg}",
                "--stitch_dzi",
                "--minimum_overlap",
                f"{round(overlap * 0.9, 2)}",
                "--resize",
                f"{stitch_resize}",
                self._scan_dir_manager.img_dir_for(scan_name),
            ],
        )

    @thing_action
    def download_zip(
        self,
        scan_name: str,
    ):
        """Update the zip to include the files left until the end, then return the
        zip file as a Blob"""
        zip_fname = self._scan_dir_manager.zip_scan(scan_name, final_version=True)
        return ZipBlob.from_file(zip_fname)
