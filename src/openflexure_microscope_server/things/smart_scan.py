import shutil
import zipfile
import threading
from typing import Mapping, Optional
import cv2
from fastapi import HTTPException
from fastapi.responses import FileResponse
import numpy as np
import numpy.polynomial.chebyshev as cheb
import os
import time
from pathlib import Path
from PIL import Image
from pydantic import BaseModel
from scipy.stats import norm
from scipy.ndimage import zoom
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit
from copy import deepcopy
from datetime import datetime, timedelta
from subprocess import CompletedProcess, Popen, PIPE, SubprocessError, run, STDOUT
from threading import Event, Thread
import glob
import json
import piexif
from labthings_fastapi.client import ThingClient
import httpx

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.invocation import CancelHook, InvocationLogger, InvocationCancelledError
from labthings_fastapi.decorators import thing_action, thing_property, fastapi_endpoint
from labthings_fastapi.outputs.blob import BlobOutput
from labthings_sangaboard import SangaboardThing
from labthings_picamera2.thing import StreamingPiCamera2
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper
from openflexure_microscope_server.things.auto_recentre_stage import RecentringThing
from .settings_manager import SettingsManager

StageDep = direct_thing_client_dependency(SangaboardThing, "/stage/")
CamDep = direct_thing_client_dependency(StreamingPiCamera2, "/camera/")
CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")
RecentreStage = direct_thing_client_dependency(RecentringThing, "/auto_recentre_stage/")

Settings = direct_thing_client_dependency(SettingsManager, "/settings/")

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
    jpeg_sizes_MB = [x / 10**3 for x in jpeg_sizes]
    stage_times = scan_data["stage_times"]
    stage_positions = scan_data["stage_positions"]
    stage_height = [pos[2] for pos in stage_positions]

    jpeg_heights = np.interp(jpeg_times, stage_times, stage_height)

    def turningpoints(lst):
        dx = np.diff(lst)
        return dx[1:] * dx[:-1] < 0

    turning = np.where(turningpoints(jpeg_heights))[0] + 1

    return jpeg_heights[turning[0] : turning[1]], jpeg_sizes_MB[turning[0] : turning[1]]


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

    # print('Movement ratio is {0} in z per lateral step. The limit is {1}'.format(round(movement_ratio, 4), round(limit,4)))
    # print(f'This is the distance between {prev_pos}, {prev_z} and {new_pos}, {new_z}')

    if movement_ratio > limit:
        return "reject"
    else:
        return "accept"


def distance_to_site(current, next):
    current = np.array(current, dtype="float64")
    next = np.array(next, dtype="float64")
    if (next[1] - current[1]) ** 2 + (next[0] - current[0]) ** 2 < 0:
        print(f"Negative distance between {next} and {current}")
    return np.sqrt(
        (next[1] - current[1]) ** 2 + (next[0] - current[0]) ** 2, dtype="float64"
    )

def steps_from_centre(current_loc, starting_loc, dx, dy):
    step_size = np.array([dx,dy])
    return np.max(np.abs(np.divide(np.subtract(current_loc, starting_loc), step_size)))

# def set_template(microscope, pos):
#     microscope.move(pos)
#     background = microscope.grab_image_array()
#     background_LUV = cv2.cvtColor(background, cv2.COLOR_RGB2LUV)

#     ch1 = (background_LUV.T[0]).flatten()
#     ch2 = (background_LUV.T[1]).flatten()
#     ch3 = (background_LUV.T[2]).flatten()

#     points = np.array([np.asarray(ch1),np.asarray(ch2),np.asarray(ch3)]).T

#     # we get the mean and standard deviation of values in each channel

#     mu, std = np.apply_along_axis(norm.fit, 0, points)
#     stats_list = np.vstack([mu, std])
#     return stats_list


def distance_to_site(current, next):
    next = np.array(next, dtype="float64")
    current = np.array(current, dtype="float64")
    return np.sqrt((next[1] - current[1]) ** 2 + (next[0] - current[0]) ** 2)

def scale_csm(csm_matrix, calibration_width, img_width):
    "Account for a calibration width that may differ from image width"
    scale = img_width / calibration_width  # Usually >1, if we calibrated at low res
    csm = np.array(csm_matrix) / scale  # Decrease the CSM if pixels are smaller]
    return csm

def generate_config(folder_path: str, positions: list, names: list, camera_to_sample_matrix, csm_calibration_width, img_width, logger):

    positions = np.array(positions)
    mean_loc = np.mean(positions, axis = 0)

    #TODO: positions from recent scans need to be 2x bigger - change to CSM res?

    camera_to_sample_matrix = scale_csm(camera_to_sample_matrix, csm_calibration_width, img_width)

    with open(os.path.join(folder_path, 'TileConfiguration.txt'), 'w') as fp:
        fp.write('# Define the number of dimensions we are working on\ndim = 2\n\n# Define the image coordinates\n')
        for i in range(len(names)):    
            loc = np.dot((positions[i] - mean_loc), np.linalg.inv(camera_to_sample_matrix))
            fp.write(f'{names[i]}; ; {loc[1], loc[0]} \n')


def raw2rggb(raw):
    """Convert packed 10 bit raw to RGGB 8 bit"""
    raw = np.asarray(raw)  # ensure it's an array
    rggb = np.empty((616, 820, 4), dtype=np.uint8)
    # rggb = np.empty((1232, 1640, 4), dtype=np.uint8) # 
    raw_w = rggb.shape[1]//2*5
    for plane, offset in enumerate([(1,1), (0,1), (1,0), (0,0)]):
        rggb[:, ::2, plane] = raw[offset[0]::2, offset[1]:raw_w+offset[1]:5]
        rggb[:, 1::2, plane] = raw[offset[0]::2, offset[1]+2:raw_w+offset[1]+2:5]
    return rggb


def rggb2rgb(rggb):
    return np.stack([rggb[..., 0], rggb[..., 1]//2 + rggb[..., 2]//2, rggb[...,3]], axis=2)


class ChannelDistributions(BaseModel):
    means: list[float]
    standard_deviations: list[float]
    colorspace: str = "LUV"

class BackgroundDetectThing(Thing):
    @thing_property
    def background_distributions(self) -> Optional[ChannelDistributions]:
        """The statistics of the background image"""
        bd = self.thing_settings.get("background_distributions", None)
        if bd:
            return ChannelDistributions(**bd)
        else:
            return None
    
    @background_distributions.setter
    def background_distributions(self, value: Optional[ChannelDistributions]) -> None:
        try:
            self.thing_settings["background_distributions"] = value.model_dump()
        except AttributeError:
            self.thing_settings["background_distributions"] = None

    @thing_property
    def tolerance(self) -> float:
        """How many standard deviations to allow for the background"""
        return self.thing_settings.get("tolerance", 7)
    
    @tolerance.setter
    def tolerance(self, value: float) -> None:
        self.thing_settings["tolerance"] = value

    @thing_property
    def fraction(self) -> float:
        """How much of the image needs to be not background to label as sample"""
        return self.thing_settings.get("fraction", 25)

    @fraction.setter
    def fraction(self, value: float) -> None:
        self.thing_settings["fraction"] = value

    def background_mask(self, image: np.ndarray) -> np.ndarray:
        """Calculate a binary image, showing whether each pixel is background

        The image should be in LUV format, the ouput will be binary with the
        same shape in the first two dimensions.
        """
        d = self.background_distributions
        if not d:
            raise RuntimeError("Background is not set: you need to calibrate background detection.")
        return np.all(
            np.abs(image - np.array(d.means)[np.newaxis, np.newaxis, :])
            < np.array(d.standard_deviations)[np.newaxis, np.newaxis, :] * self.tolerance,
            axis=2,
        )
    
    @thing_action
    def background_fraction(self, cam: CamDep) -> float:
        """Determine what fraction of the current image is background
        
        This action will acquire a new image from the preview stream, then
        evaluate whether it is foreground or background, by comparing it
        too the saved statistics. This is done on a per-pixel basis, and
        the returned value (between 0 and 100) is the fraction of the image
        that is background.
        """
        current_image = cam.grab_jpeg()
        current_image = np.array(Image.open(current_image.open()))

        # we're working in the LUV colourspace as it collect colours together in a human-intuitive way
        current_image_LUV = cv2.cvtColor(current_image, cv2.COLOR_RGB2LUV)
        mask = self.background_mask(current_image_LUV)
        return np.count_nonzero(mask) / np.prod(mask.shape) * 100

    @thing_action
    def image_is_sample(self, cam: CamDep) -> bool:
        """Label the current image as either background or sample"""
        b_fraction = self.background_fraction(cam)
        fraction_threshold = self.fraction

        return (100 - b_fraction) > fraction_threshold
    
    @thing_action
    def set_background(self, cam: CamDep):
        """Grab an image, and use its statistics to set the background
        
        This should be run when the microscope is looking at an empty region,
        and will calculate the mean and standard deviation of the pixel values
        in the LUV colourspace. These values will then be used to compare
        future images to the distribution, to determine if each pixel is
        foreground or background.
        """
        background = cam.grab_jpeg()
        background = np.array(Image.open(background.open()))

        # we're working in the LUV colourspace as it collect colours together in a human-intuitive way
        background_LUV = cv2.cvtColor(background, cv2.COLOR_RGB2LUV)

        ch1 = (background_LUV.T[0]).flatten()
        ch2 = (background_LUV.T[1]).flatten()
        ch3 = (background_LUV.T[2]).flatten()

        points = np.array([np.asarray(ch1), np.asarray(ch2), np.asarray(ch3)]).T

        # we get the mean and standard deviation of values in each channel
        mu, std = np.apply_along_axis(norm.fit, 0, points)

        self.background_distributions = ChannelDistributions(
            means = mu.tolist(),
            standard_deviations = std.tolist(),
            colorspace = "LUV",
        )

    @property
    def thing_state(self) -> Mapping:
        bd = self.background_distributions
        return {
            "background_distributions": bd.model_dump() if bd else None,
            "tolerance": self.tolerance,
            "fraction": self.fraction,
        }

    
BackgroundDep = direct_thing_client_dependency(BackgroundDetectThing, "/background_detect/")


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
    """"Summary information about a scan folder"""
    name: str
    created: datetime
    modified: datetime
    number_of_images: int
    dzi: Optional[str]


DOWNLOADABLE_SCAN_FILES = (
    "images.zip",
    "stitched_thumbnail.jpg"
)

class JPEGBlob(BlobOutput):
    media_type = "image/jpeg"

class ZipBlob(BlobOutput):
    media_type = "application/zip"

class SmartScanThing(Thing):
    def __init__(self, path_to_openflexure_stitch: str):
        self._script = path_to_openflexure_stitch
        self._preview_stitch_popen_lock = threading.Lock()
        self._correlate_popen_lock = threading.Lock()
        self._scan_lock = threading.Lock()
    
    @property
    def scans_folder_path(self) -> str:
        """This folder will hold all the scans we do."""
        # TODO: This should be determined using sensible configuration.
        # If the working directory is `/var/openflexure` this will result
        # in scans being saved at `/var/openflexure/scans/`
        return "/mnt/openflexure-data/scans"
    
    @thing_action
    def mount_usb_storage(self):
        """Mount (start using) a USB stick used for storing scans"""
        if self.usb_storage_mounted:
            return
        try:
            run(["mount", "/mnt/openflexure-data"], check=True)
        except SubprocessError:
            raise IOError(
                    "Cannot access scans: most likely this means the microscope "
                    "is configured to save to a USB drive, and no USB drive "
                    "is inserted."
                )

    @thing_action
    def eject_usb_storage(self):
        """Eject a USB stick used for storing scans"""
        if self.usb_storage_mounted:
            run(["umount", "/mnt/openflexure-data"], check=True)

    @thing_property
    def usb_storage_mounted(self) -> bool:
        """Check whether a USB storage device is mounted for storing scans on."""
        p = run(["mountpoint", "/mnt/openflexure-data"], check=False)
        return p.returncode == 0
    
    _latest_scan_name = None
    @thing_property
    def latest_scan_name(self) -> Optional[str]:
        """The name of the last scan to be started."""
        return self._latest_scan_name

    def scan_folder_path(self, scan_name: Optional[str]=None):
        """The path to the scan folder with a given name"""
        if not scan_name:
            if not self.latest_scan_name:
                raise IOError("There is no latest scan to return")
            scan_name = self.latest_scan_name
        return os.path.join(self.scans_folder_path, scan_name)
    
    def new_scan_folder(self, scan_name: str="scan") -> str:
        """Create a new empty folder, into which we can save scan images
        
        The folder will be named `{scan_name}_000001/` where the number is
        zero-padded to be 6 digits long (to allow correct sorting if the
        scans are ordered alphanumerically).
        
        Note that if you have discontinuous numbering (e.g. you've got scans
        numbered 1 through 10, but you deleted scan 5), then the gaps will
        get filled in - so there's no guarantee, for now, that the numbers
        will correspond to order of creation. This may change in the future.
        """
        self.mount_usb_storage()
        if not os.path.exists(self.scans_folder_path):
            os.makedirs(self.scans_folder_path)
        if not scan_name:
            scan_name = "scan"
        for j in range(9999):
            folder_path = os.path.join(self.scans_folder_path, f"{scan_name}_{j:04}")
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                self._latest_scan_name = os.path.basename(folder_path)
                return folder_path
        raise FileExistsError("Could not create a new scan folder: all names in use!")
    
    def function(
            self,
            data,
            a,
            b,
            c,
            d,
            e
        ):
        x = data[0]
        y = data[1]
        return a*x**2 + b*y**2 + c*x + d*y + e

    def fit_next_z(
            self,
            loc,
            focused_path
        ):
        #TODO test when to reject this fit - like if we only have a couple of points in one axis, or if curvature is positive
        x_data = []
        y_data = []
        z_data = []
        for item in focused_path:
            x_data.append(item[0])
            y_data.append(item[1])
            z_data.append(item[2])
        parameters, covariance = curve_fit(self.function, [x_data, y_data], z_data, [-1, 1, -1, 1, 1], method='trf')
        next_z = self.function(loc, *parameters)
        return next_z
    
    def move_to_next_point(
            self,
            stage: StageDep,
            logger: InvocationLogger,
            path: list[list[int]],
            focused_path: list[list[int]],
            csm: CSMDep,
            cam: CamDep,
            current_pos: list[int]
        ) -> list[int]:
        """Remove the first point from the path, and move there.
        
        This will move to the next XY position in `path`, taking the `z` value
        either from the current z value of the stage, or from `focused_path`.

        Returns the point we have moved to.
        """
        loc = [path[0][0], path[0][1]]
        path.remove(path[0])
        logger.debug(f"Moving to {loc}")
        x_positions = len(set([i[0] for i in focused_path]))
        y_positions = len(set([i[1] for i in focused_path]))
        if x_positions >= 3 and y_positions >= 3:
            z = int(self.fit_next_z(loc, focused_path))
            # z = z - ((self.stack_test_height-1)/2 +4)*self.stack_dz
        elif len(focused_path) > 1:
            z_index = closest(loc, focused_path)
            z = int(focused_path[z_index][2]) # - ((self.stack_test_height-1)/2 +6)*self.stack_dz
        else:
            z = stage.position["z"]  # - ((self.stack_test_height-1)/2 +7)*self.stack_dz
        stage.move_absolute(
            x=stage.position["x"], y = stage.position["y"], z = z - 35
        )

        x_move = loc[0] - current_pos[0]
        y_move = loc[1] - current_pos[1]

        pixel_move = np.dot(
            np.array([y_move, x_move]),
            np.linalg.inv(np.array(csm.image_to_stage_displacement_matrix))
        )

        if abs(pixel_move[0]) > abs(pixel_move[1]):
            pixel_move[1] = 0
        else:
            pixel_move[0] = 0

        closed_loop_ratio = 1.0

        csm.certify_move_in_image_coordinates(
            stage = stage,
            cam = cam,
            logger = logger,
            x = -pixel_move[0]*closed_loop_ratio,
            y = -pixel_move[1]*closed_loop_ratio,
            threshold = 10
        )

        # TODO: when do we just want to use this? Definitely if the current FOV was background
        # csm.move_in_image_coordinates(
        #     stage = stage,
            # x = -pixel_move[0]*(1-closed_loop_ratio),
            # y = -pixel_move[1]*(1-closed_loop_ratio)
        # )

        return loc + [z]

    def update_thumbnail(self, images_folder, logger):
        target_width = 200
    
        file_path = os.path.join(images_folder, 'stitched.jpg')
        if os.path.isfile(file_path):
            img = cv2.imread(file_path, -1)
        else:
            file_path = os.path.join(images_folder, 'stitched_from_stage.jpg')
            if os.path.isfile(file_path):
                img = cv2.imread(file_path, -1)
            else:
                logger.debug(f'No scan image to downsample yet')
                return 0
        try:
            img_height, img_width = img.shape[:2]
            ratio = target_width / img_width

            thumbnail = cv2.resize(img, dsize=(0,0), fx=ratio, fy=ratio)
            cv2.imwrite(os.path.join(images_folder, 'stitched_thumbnail.jpg'), thumbnail)
        except:
            return 0
        return 1

        
    @fastapi_endpoint(
            "get",
            "scans/stitched_thumbnail.jpg",
            responses = {
                200: {
                    "description": "A thumbnail-quality stitched image",
                    "content": {"image/jpeg": {}}
                },
                404: {"description": "File not found"}
            },
        )
    def get_scan_thumbnail(self, scan_name: str) -> FileResponse:
        """Retrieve a file from a scan.
        
        This endpoint allows files to be downloaded from a scan.
        """
        path = os.path.join(self.scans_folder_path, scan_name, "images", "use", "stitched_thumbnail.jpg")
        if not os.path.isfile(path):
            raise HTTPException(404, "File not found")
        return FileResponse(path)


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
        recentre: RecentreStage,
        settings: Settings,
        scan_name: str=""
    ):
        """Move the stage to cover an area, taking images that can be tiled together.

        The stage will move in a pattern that grows outwards from the starting point,
        stopping once it is surrounded by "background" (as detected by the 
        background_detect Thing).

        Input:

        * `overlap` is the fraction by which images should overlap, i.e. 
          `0.3` means we will move by 70% of the field of view each time.
        """
        # Define these variables so we can use them in the finally: block
        # (after testing they are not None)
        # cam_settings = ThingClient.from_url("/camera/", httpx.Client(base_url="http://localhost:5000/", trust_env=False, timeout=20))
        # cam.sensor_mode = {"output_size": [3280, 2464], "bit_depth":10}
        cam.sensor_mode = {"output_size": [1640, 1232], "bit_depth":10}

        scan_folder = None
        images_folder = None
        starting_position = None
        capture_thread = None
        # Temporary, for Tanzania trial: ensure a USB disk is connected
        try:
            self.mount_usb_storage()
        except IOError:
            logger.error(
                "The USB storage device is not connected. You must connect "
                "it before starting a scan."
            )
            time.sleep(1)
            raise
        
        self._scan_lock.acquire(timeout=0.1)
        start_time = time.strftime("%H:%M:%S")
        if self.stack_height % 2 == 0:
            logger.error("Stack height should be odd")
            raise RuntimeError(
                "Stack height should be odd"
            )
        logger.info(f'Starting scan at {start_time}')
        start_time_seconds = time.time()
        try:
            scan_folder = self.new_scan_folder(scan_name)
            scan_name = os.path.basename(scan_folder)
            images_folder = os.path.join(scan_folder, "images")
            os.mkdir(images_folder)
            use_folder = os.path.join(images_folder, "use")
            os.mkdir(use_folder)
            logger.info(f"Saving images to {images_folder}")
            # Before anything else, check that we've got a background set
            # It's annoying to have to wait to find out!
            max_dist = self.max_range
            
            if self.autofocus_dz == 0:
                logger.info(f'Running scan without autofocus')
            elif self.autofocus_dz <= 200:
                logger.warning(f'Your dz range is {self.autofocus_dz} steps, which is too short to attempt to focus. Running without autofocus')

            if self.skip_background:
                d = background_detect.background_distributions
                if not d:
                    raise RuntimeError("Background is not set: you need to calibrate background detection.")
            else:
                logger.warning(
                    "This scan will run in a spiral from the starting point "
                    f"until you cancel it, or until it has moved by {max_dist} steps "
                    "in every direction. Make sure you watch it run to stop it leaving "
                    "the area of interest, or (worse) leading the microscope's range "
                    "of motion."
                    )
            names = []
            positions = []

            # Record the starting position so we can move back there afterwards
            starting_position = stage.position

            autofocus.looping_autofocus(dz = self.autofocus_dz)

            r = cam.grab_jpeg()
            arr = np.array(Image.open(r.open()))
            if csm.image_resolution is None:
                raise RuntimeError(
                    "Camera-stage mapping is not calibrated. This is required before "
                    "scans can be carried out."
                )
            if list(arr.shape[:2]) != [int(i) for i in csm.image_resolution]:
                logger.error(
                    f"Images are, by default, {arr.shape[:2]}, but the CSM was "
                    f"calibrated at {csm.image_resolution}."
                )

            # Here, we calculate the x and y step size based on the desired overlap
            # TODO: Consider using CSM calibration size instead
            # TODO: generalise to have 2D displacements for x and y (as the
            # camera and stage may not be aligned).
            CSM = csm.image_to_stage_displacement_matrix
            csm_calibration_width = csm.last_calibration["image_resolution"][1]

            overlap = self.overlap

            steps_per_pixel_x = CSM[0][1]
            steps_per_pixel_y = CSM[1][0]

            dx = int(steps_per_pixel_x * 820 * (1 - overlap))
            dy = int(steps_per_pixel_y * 616 * (1 - overlap))

            logger.info(dx)
            logger.info(dy)

            # dx = int(np.abs(np.dot(np.array([0, arr.shape[1] * (1 - overlap)]), CSM)[0]))
            # dy = int(np.abs(np.dot(np.array([arr.shape[0] * (1 - overlap), 0]), CSM)[1]))

            logger.info(f"Running a scan with an overlap between images of {overlap}")
            logger.debug(f"Overlap of {overlap}, movements of {dx}, {dy}")
            logger.debug(f"Autofocus range is {self.autofocus_dz}")
            logger.debug(f"Skipping background is {self.skip_background}")

            # construct a 2D scan path
            path = [[stage.position["x"], stage.position["y"]]]

            focused_path = []  # This holds a list of all points where focus succeeded
            true_path = []  # This holds a list of all points visited
            i = 0
            ids = []
            start_time = time.strftime("%H_%M_%S-%d_%m_%Y")

            data = {
                'scan_name' : scan_name,
                'overlap' : overlap,
                'autofocus range' : self.autofocus_dz,
                'dx' : dx,
                'dy' : dy,
                'start time' : start_time,
                'skipping background' : self.skip_background,
                'stack_dz' : self.stack_dz,
                'stack_height' : self.stack_height,
                'microscope_hostname': settings.hostname
            }

            with open(os.path.join(images_folder, 'scan_inputs.json'), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            # We will capture images and process them with this function, defined once here.
            # Most of the variables it needs will be "baked in" so the arguments are just the ones
            # that change each iteration.
            # We also pre-calculate a normalisation image based on the LST and white balance
            raw_image = cam.capture_array(stream_name="raw")
            #TODO: assert the image is 10-bit packed, or deal with other formats!
            norm_inputs = self.set_normalisation(cam = cam, raw_image = raw_image)
            lum = norm_inputs['luminance']
            Cr = norm_inputs['Cr']
            Cb = norm_inputs['Cb']
            gr = norm_inputs["gain_red"]
            gb = norm_inputs["gain_blue"]
            rgb = norm_inputs["rgb"]
            
            G = 1/lum
            R = G/Cr/gr*np.min(Cr)  # The extra /np.max(Cr) emulates the quirky handling of Cr in
            B = G/Cb/gb*np.min(Cb)   # the picamera2 pipeline
            white_norm_lores = np.stack([R, G, B], axis=2)
            zoom_factors = [i/n for i, n in zip(rgb[...,:3].shape, white_norm_lores.shape)]
            white_norm = zoom(white_norm_lores, zoom_factors, order=1)[:rgb.shape[0], :rgb.shape[1], :]  # Could use some work
            colour_correction_matrix = np.array(cam.colour_correction_matrix).reshape((3,3))
            contrast_algorithm = cam.tuning["algorithms"][9]["rpi.contrast"]
            gamma = np.array(contrast_algorithm["gamma_curve"]).reshape((-1,2))
            gamma_8bit = interp1d(gamma[:, 0]/255, gamma[:, 1]/255)

            capture_inputs = {}
            capture_inputs['norm_inputs'] = norm_inputs
            capture_inputs['colour_correction_matrix'] = colour_correction_matrix
            capture_inputs['gamma_8bit'] = gamma_8bit
            capture_inputs['white_norm'] = white_norm

            def process_raw_image(img):
                normed = img/white_norm
                corrected = np.dot(colour_correction_matrix, normed.reshape((-1, 3)).T).T.reshape(normed.shape)
                corrected[corrected < 0] = 0
                corrected[corrected > 255] = 255
                return gamma_8bit(corrected)
            logger.debug(
                f"Generated normalisation image with shape {white_norm.shape}, "
                f"max {white_norm.max(axis=(0,1))}, min {white_norm.min(axis=(0,1))}"
            )
            
            current_pos = path[0]

            # At the start of the loop, we simultaneously capture an image and move to the next scan point.
            # We skip capturing on the first run, because we've not focused yet - and also we skip capturing if
            # it looks like background.
            while len(path) > 0:
                loc = self.move_to_next_point(stage, logger, path=path, focused_path=focused_path, csm = csm, cam = cam, current_pos = current_pos)
                current_pos = loc
                if not self.preview_stitch_running():
                    preview_csm = CSM
                    preview_csm[0][0] = 0
                    preview_csm[1][1] = 0
                    self.preview_stitch_start(os.path.join(images_folder, 'use'), preview_csm)
                # if self.stitch_automatically:
                if not self.correlate_running():
                    self.correlate_start(os.path.join(images_folder, 'use'), overlap=overlap)

                ensure_free_disk_space(scan_folder)

                # Check if the image is background
                if self.skip_background:
                    image_is_sample = background_detect.image_is_sample()
                    # image_is_sample = cam.grab_jpeg_size(stream_name="lores") >= 18000
                    # logger.info(cam.grab_jpeg_size(stream_name="lores"))
                else:
                    image_is_sample = True

                # if more than 92% of the image is background, treat it as background and continue
                if not image_is_sample:
                    logger.info(f"Skipping {stage.position} as it is {round(background_detect.background_fraction(),0)}% background.")
                    capture_image = False
                else:
                    capture_image = True
                    # if not, it's sample. run an autofocus and use the updated height
                    new_pos = [
                        [current_pos[0] - dx, current_pos[1]],
                        [current_pos[0] + dx, current_pos[1]],
                        [current_pos[0], current_pos[1] - dy],
                        [current_pos[0], current_pos[1] + dy],
                    ]
                    for pos in new_pos:
                        if (
                            pos not in [sublist[:2] for sublist in true_path]
                            and pos not in path
                        ):
                            path.append(pos)

                    focused_height, new_save_thread = self.smart_stack(cancel = cancel,
                                    logger = logger,
                                    autofocus = autofocus,
                                    stage = stage,
                                    cam = cam,
                                    metadata_getter = metadata_getter,
                                    images_folder = images_folder,
                                    start = 'base',
                                    autofocus_dz = self.autofocus_dz,
                                    image_stack_height = self.stack_height,
                                    stack_dz = self.stack_dz,
                                    focused_path = focused_path,
                                    capture_inputs = capture_inputs,
                                    current_pos = current_pos
                                    )
                    # save images in the background
                    if capture_thread:  # wait for the previous capture to be saved, i.e. don't leave more than one image saving in the background
                        if capture_thread.is_alive():
                            wait_start = time.time()
                            capture_thread.join()
                            wait_time = time.time() - wait_start
                            logger.info(f"Waited {wait_time:.1f}s for the previous capture to finish saving.")
                    capture_thread = new_save_thread
                    capture_thread.start()

                    focused_path.append([loc[0], loc[1], focused_height])

                # add the current position to the list of all positions visited
                true_path.append([loc[0], loc[1], focused_height])
                
                if len(focused_path) == self.max_image_count:
                    logger.info(f'Now captured {len(focused_path)} images, ending scan.')
                    break

                #if len(names) > 1:
                #    generate_config(images_folder, positions, names, CSM, csm_calibration_width, img_width, logger)

                temp_path = []

                self.update_thumbnail(os.path.join(images_folder, 'use'), logger)

                for i in path:
                    if distance_to_site(i, true_path[0][:2]) < max_dist:
                        temp_path.append(i)
                    else:
                        logger.info(f'Rejected moving to {i} as it is out of range')
                path = temp_path.copy()
                path = sorted(path, key=lambda x: (steps_from_centre(x, true_path[0][:2], dx, dy), distance_to_site(loc[:2], x)))
                self.create_zip_of_scan(logger = logger, scan_name = scan_folder.split('scans/')[1], download_zip = False)

        except InvocationCancelledError:
            logger.error("Stopping scan because it was cancelled.")
        except NotEnoughFreeSpaceError as e:
            logger.error(
                f"Stopping scan to avoid filling up the disk: {e}",
                exc_info=e,
            )
            raise e
        except Exception as e:
            logger.error(
                f"The scan stopped because of an error: {e}",
                "We will attempt to stitch and archive the images acquired "
                "so far.",
                exc_info=e,
            )
            raise e
        finally:
            if capture_thread:
                capture_thread.join()
            try:
                #TODO print where the centre actually is
                logger.info("Returning to starting position.")
                if starting_position is not None:
                    logger.info(f'Scan duration was {timedelta(seconds = round(time.time()-start_time_seconds))} seconds. Captured {len(focused_path)} images')
                    stage.move_absolute(**starting_position, block_cancellation=True)
                    autofocus.looping_autofocus(dz = self.autofocus_dz)
            finally:
                self._scan_lock.release()
            self.create_zip_of_scan(logger = logger, scan_name = scan_folder.split('scans/')[1], download_zip = False)
            logger.info("Processing images, please wait")
            self.preview_stitch_wait()
            self.correlate_wait()
            try:
                if scan_folder and self.stitch_automatically:
                    logger.info("Stitching final image (may take some time)...")
                    self.stitch_scan(logger, os.path.basename(scan_folder), overlap=overlap)
            except SubprocessError as e:
                logger.error(f"Stitching failed: {e}", exc_info=e)

    @thing_property
    def max_range(self) -> int:
        """The maximum distance from the centre of the scan before we break"""
        return self.thing_settings.get("max_range", 45000)

    @max_range.setter
    def max_range(self, value: int) -> None:
        self.thing_settings["max_range"] = value

    @thing_property
    def max_image_count(self) -> int:
        """The maximum number of images to capture before we break"""
        return self.thing_settings.get("max_image_count", 225)

    @max_image_count.setter
    def max_image_count(self, value: int) -> None:
        self.thing_settings["max_image_count"] = value

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
        return self.thing_settings.get("overlap", 0.35)

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
        if not os.path.isdir(self.scans_folder_path):
            self.mount_usb_storage()
        if not os.path.isdir(self.scans_folder_path):
            return scans
        for f in os.listdir(self.scans_folder_path):
            path = os.path.join(self.scans_folder_path, f)
            if os.path.isdir(path):
                images_folder = os.path.join(path, "images")
                if os.path.isdir(images_folder):
                    number_of_images = len(os.listdir(images_folder))
                else:
                    number_of_images = 0
                if os.path.isfile(os.path.join(images_folder, "use", "stitched.dzi")):
                    dzi = "images/use/stitched.dzi"
                else:
                    dzi = None
                scans.append(
                    ScanInfo(
                        name = f,
                        created = os.path.getctime(path),
                        modified = os.path.getmtime(path),
                        number_of_images = number_of_images,
                        dzi = dzi,
                    )
                )
        return scans
    
    @fastapi_endpoint(
            "get",
            "scans/{scan_name}/{file:path}",
            responses = {
                200: {
                    "description": "Successfully downloading file",
                    "content": {"*/*": {}}
                },
                403: {"description": "Filename not permitted"},
                404: {"description": "File not found"}
            },
        )
    def get_scan_file(self, scan_name: str, file: str) -> FileResponse:
        """Retrieve a file from a scan.
        
        This endpoint allows files to be downloaded from a scan. For security
        reasons, there is a list of allowable filenames, and paths with additional
        slashes are not permitted.
        """
        #if file not in DOWNLOADABLE_SCAN_FILES:
        #    raise HTTPException(
        #        403, f"You may only download files named {DOWNLOADABLE_SCAN_FILES}"
        #    )
        scan = Path(self.scans_folder_path) / scan_name
        path = scan / file
        if scan not in path.parents:
            raise HTTPException(403, "File not permitted")
        if not os.path.isfile(path):
            raise HTTPException(404, "File not found")
        return FileResponse(path)
    
    @fastapi_endpoint(
        "delete",
        "scans/{scan_name}",
        responses = {
            200: {"description": "Successfully deleted scan"},
            404: {"description": "Scan not found"},
        },
    )
    def delete_scan(self, scan_name: str) -> None:
        """Delete all files from a scan.
        
        This endpoint allows scans to be deleted from disk.
        """
        path = os.path.join(self.scans_folder_path, scan_name)
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
    
    def images_folder(self, scan_name: Optional[str]=None) -> str:
        scan_folder = self.scan_folder_path(scan_name=scan_name)
        return os.path.join(scan_folder, "images")
    
    @property
    def latest_preview_stitch_path(self):
        """The path of the latest preview stitched image"""
        stage_path = os.path.join(self.images_folder(), "use", "stitched_from_stage.jpg")
        stitch_path = os.path.join(self.images_folder(), "use", "stitched.jpg")
        # The lines below are a hack so we see the stitched image at the end of a scan.
        if os.path.exists(stage_path) and os.path.exists(stitch_path):
            if os.path.getmtime(stitch_path) > os.path.getmtime(stage_path):
                return stitch_path
        return os.path.join(self.images_folder(), "use", "stitched_from_stage.jpg")

    @thing_property
    def latest_preview_stitch_time(self) -> Optional[datetime]:
        """The modification time of the latest preview image
        
        This will return `null` if there is no preview image to return.
        """
        try:
            fpath = self.latest_preview_stitch_path
            if os.path.exists(fpath):
                return os.path.getmtime(fpath)
        except IOError:
            return None
        return None
        
    @fastapi_endpoint(
            "get",
            "latest_preview_stitch.jpg",
            responses = {
                200: {
                    "description": "A preview-quality stitched image",
                    "content": {"image/jpeg": {}}
                },
                404: {"description": "File not found"}
            },
        )
    def get_latest_preview(self, logger:InvocationLogger) -> FileResponse:
        """Retrieve the latest preview image.
        """
        path = self.latest_preview_stitch_path
        if not os.path.isfile(path):
            raise HTTPException(404, "File not found")
        return FileResponse(path)
    
    _preview_stitch_popen = None
    def preview_stitch_start(self, images_folder: str, preview_csm) -> None:
        """Start stitching a preview of the scan in a subprocess"""
        if self.preview_stitch_running():
            raise RuntimeError("Only one subprocess is allowed at a time")
        with self._preview_stitch_popen_lock:
            self._preview_stitch_popen = Popen(
                [self._script, "--stitching_mode", "only_stage_stitch", "--csm_matrix", str(preview_csm), images_folder]
            )
            #TODO: remove the previous scan preview when a new one starts

    def preview_stitch_running(self) -> bool:
        """Whether there is a preview stitch running in a subprocess"""
        with self._preview_stitch_popen_lock:
            if self._preview_stitch_popen is None:
                return False
            if self._preview_stitch_popen.poll() is None:
                return True
            return False
    
    def preview_stitch_wait(self):
        if self.preview_stitch_running():
            with self._preview_stitch_popen_lock:
                self._preview_stitch_popen.wait()
        
    _correlate_popen = None
    def correlate_start(self, images_folder: str, overlap: float = 0.1) -> None:
        """Start stitching a preview of the scan in a subprocess"""
        if self.correlate_running():
            raise RuntimeError("Only one subprocess is allowed at a time")
        with self._correlate_popen_lock:
            self._correlate_popen = Popen(
                [self._script, "--stitching_mode", "only_correlate", "--minimum_overlap", f"{round(overlap*0.9, 2)}", "--resize", "1", "--max_stage_discrepancy", "200", images_folder]
            )

    def correlate_running(self) -> bool:
        """Whether there is a preview stitch running in a subprocess"""
        with self._correlate_popen_lock:
            if self._correlate_popen is None:
                return False
            if self._correlate_popen.poll() is None:
                return True
            return False
    
    def correlate_wait(self):
        if self.correlate_running():
            with self._correlate_popen_lock:
                self._correlate_popen.wait()

    def run_subprocess(
            self, logger: InvocationLogger, cmd: list[str],
        ) -> CompletedProcess:
        """Run a  subprocess and log any output"""
        logger.debug(f"Running command in subprocess: `{' '.join(cmd)}`")

        
        p = Popen(cmd, stdout=PIPE, stderr = STDOUT, bufsize=1, universal_newlines=True)
        os.set_blocking(p.stdout.fileno(), False) 
        while p.poll() == None:
            try:
                output = p.stdout.readline()
                if output != "" and output != None:
                    logger.info(output)  
            except:
                pass

        for line in p.stdout:
            try:
                output = p.stdout.readline()
                if output != "" and output != None:
                    logger.info(output)  
            except:
                pass

        logger.info('Stitching complete')
        return p

    @thing_action
    def stitch_scan(self, logger: InvocationLogger, scan_name: Optional[str]=None, overlap: float = 0.0) -> None:
        """Generate a stitched image based on stage position metadata"""
        images_folder = self.images_folder(scan_name=scan_name)

        if self.stitch_tiff:
            tiff_arg = '--stitch_tiff'
        else:
            tiff_arg = '--no-stitch_tiff'

        if overlap == 0.0:
            try:
                with open(os.path.join(images_folder, 'scan_inputs.json')) as data_file:
                    data_loaded = json.load(data_file)
                overlap = data_loaded['overlap']
            except:
                overlap = 0.1
        self.run_subprocess(logger, [self._script, "--stitching_mode", "all", f"{tiff_arg}", "--minimum_overlap", f"{round(overlap*0.9,2)}", "--resize", "1", "--stitch_dzi", os.path.join(images_folder, 'use')])
    
    @thing_action
    def create_zip_of_scan(self, logger: InvocationLogger, scan_name: Optional[str]=None, download_zip = True) -> ZipBlob:
        """Generate a zip file that can be downloaded, with all the scan files in it."""
        images_folder = self.images_folder(scan_name=scan_name)
        scan_folder = self.scan_folder_path(scan_name=scan_name)
        if scan_folder != os.path.dirname(images_folder) or os.path.basename(images_folder) != "images":
            logger.error(
                "There is a problem with filenames, the archive may be incorrect."
                f"scan_folder: {scan_folder}, images_folder: {images_folder}."
            )
        if not os.path.isdir(images_folder):
            raise FileNotFoundError(f"Tried to make a zip archive of {images_folder} but it does not exist.")

        zip_fname = f'{os.path.join(scan_folder, "images")}.zip'

        # Create an empty zip file - we don't want to autofill it with files,
        # as some of them should only be added at the end (as we can't overwrite)
        # them once they change
        if not os.path.isfile(zip_fname):
            with zipfile.ZipFile(zip_fname, mode="w") as zip:
                pass
            
        # get a list of files in the existing zip    
        current_zip = self.get_files_in_zip(zip_fname)

        # get a list of files in the folder we're zipping
        folder_path = self.scan_folder_path(scan_name)
        files = glob.glob(folder_path + '/**/*', recursive=True)
        files = [i.split(f'{folder_path}/')[1] for i in files]

        # This is a list of file names that are updated as the scan goes,
        # and should only be zipped at the end of the scan - otherwise they'll
        # be appended on every loop as we can't overwrite files in the zip
        files_to_delay = ['TileConfiguration', 'tiling_cache', 'stitched.jp', 'stitched_from', 'stitched.om']
        stitch_name = ""
        tiff_name = ""

        with zipfile.ZipFile(zip_fname, mode="a") as zip:
            for file in files:
                if 'stitched.jp' in file:
                    stitch_name = os.path.split(file)[1]
                if '.ome.tiff' in file:
                    tiff_name = os.path.split(file)[1]
                if any(banned_name in file for banned_name in files_to_delay):
                    # logger.info(f'we only add {file} into zip at the end of the scan')
                    pass
                elif file in current_zip:
                    # logger.info(f'{file} is already in zip')
                    pass
                elif ".zip" in file: # or 'raw' in file:
                    # logger.info('Not adding the .zip to itself')
                    pass
                else:
                    logger.debug(f'appending {file} to zip')
                    zip.write(os.path.join(folder_path, file), arcname=file)
                    

        images_folder = os.path.join(folder_path, 'images','use')
        # Promote key files to the top level of the zip only at the end of the scan (when downloading)
        # and finally zip some of the final files
        # TODO: if you download multiple times, you get duplicate files - is this a problem?
        if download_zip:
            with zipfile.ZipFile(zip_fname, mode="a") as zip:
                for fname in ["stitched_from_stage.jpg", stitch_name, tiff_name]:
                    fpath = os.path.join(images_folder, fname)
                    if os.path.isfile(fpath):
                        logger.debug(f'copying {fpath} to upper level')
                        zip.write(fpath, arcname=fname)
                for file in files:
                    if any(banned_name in file for banned_name in files_to_delay):
                        logger.debug(f'we are finally adding {file} into zip')
                        zip.write(os.path.join(folder_path, file), arcname=file)
            logger.info('About to download zip')
            return ZipBlob.from_file(zip_fname)

    @thing_action
    def get_files_in_zip(self, zip_path):
        """List the relative paths of all files and folders in the zip folder specified"""
        zip = zipfile.ZipFile(zip_path)
        zip = [os.path.normpath(i) for i in zip.namelist()]
        
        return zip

    def set_normalisation(self, cam, raw_image = None):
        if raw_image is None:
            raw_image = cam.capture_array(stream_name="raw")
        #TODO: assert the image is 10-bit packed, or deal with other formats!
        rgb = rggb2rgb(raw2rggb(raw_image))
        lst = dict(cam.lens_shading_tables)
        lum = np.array(lst["luminance"])
        Cr = np.array(lst["Cr"])
        Cb = np.array(lst["Cb"])
        gr, gb = cam.colour_gains

        norm_inputs = {
            "luminance": lum,
            "Cr": Cr,
            "Cb": Cb,
            "gain_red": gr,
            "gain_blue": gb,
            "rgb": rgb,
        }
        return norm_inputs

    @thing_action
    def smart_stack(
        self,
        cancel: CancelHook,
        logger: InvocationLogger,
        autofocus: AutofocusDep,
        stage: StageDep,
        cam: CamDep,
        metadata_getter: GetThingStates,
        images_folder,
        start = 'base',
        autofocus_dz = 2000,
        image_stack_height = 9,
        stack_dz = 50,
        focused_path = [],
        capture_inputs = None,
        current_pos = 0
    ):
        # This is the number of images we test.
        stack_height = self.stack_test_height
        undershoot = (self.stack_test_height-1)/2 + 5
        
        norm_inputs = capture_inputs['norm_inputs']
        lum = norm_inputs['luminance']
        Cr = norm_inputs['Cr']
        Cb = norm_inputs['Cb']
        gr = norm_inputs["gain_red"]
        gb = norm_inputs["gain_blue"]
        rgb = norm_inputs["rgb"]

        gamma_8bit = capture_inputs["gamma_8bit"]
        colour_correction_matrix = capture_inputs["colour_correction_matrix"]
        white_norm = capture_inputs["white_norm"]


        def process_raw_image(img):
            normed = img/white_norm
            corrected = np.dot(colour_correction_matrix, normed.reshape((-1, 3)).T).T.reshape(normed.shape)
            corrected[corrected < 0] = 0
            corrected[corrected > 255] = 255
            return gamma_8bit(corrected)


        def capture_image(stage):
            """Capture an image and save it to disk
            
            This will set the event `acquired` once the image has been acquired, so
            that the stage may be moved while it's saved.
            """
            try:
                capture_start = time.time()
                metadata = metadata_getter()
                metadata['/stage/']['true_stage_position'] = dict(stage.position)
                metadata['/stage/']['position']['x'] = current_pos[0]
                metadata['/stage/']['position']['y'] = current_pos[1]
                metadata['/stage/']['position']['z'] = stage.position['z']
                raw_image = cam.capture_array(stream_name="raw")
                return raw_image, metadata
            except Exception as e:
                logger.error(f"An error occurred while capturing: {e}", exc_info=e)
                return 0, 0

        def save_capture(name, raw_image, metadata, current_pos, processed = None):
            try:    
                # Save the raw image
                np.savez(os.path.join(images_folder, name + ".npz"), raw_image=raw_image, **norm_inputs)
                # Process it into 8 bit RGB
                processed = process_raw_image(rggb2rgb(raw2rggb(raw_image)))
                processed[processed > 255] = 255
                processed[processed < 0] = 0
                img = Image.fromarray(processed.astype(np.uint8), mode="RGB")
                img.save(
                    os.path.join(images_folder, name),
                    quality=100,
                    subsampling=0
                )
                exif_dict = piexif.load(os.path.join(images_folder, name))
                exif_dict["Exif"][piexif.ExifIFD.UserComment] = json.dumps(
                    metadata
                ).encode("utf-8")
                piexif.insert(piexif.dump(exif_dict), os.path.join(images_folder, name))
                save_time = time.time()
            except Exception as e:
                logger.error(f"An error occurred while saving {name}: {e}", exc_info=e)

        x_positions = len(set([i[0] for i in focused_path]))
        y_positions = len(set([i[1] for i in focused_path]))
        if x_positions < 3 or y_positions < 3:
            logger.debug("We're just starting, so doing a full autofocus")
            undershoot_z = - ((self.stack_test_height-1)/2 +6)*self.stack_dz - 300
        else:
            logger.debug("We've got a good idea where we should be skipping autofocus")
            undershoot_z = - ((self.stack_test_height-1)/2 +4)*self.stack_dz - 300
        stage.move_relative(z = undershoot_z)
        stage.move_relative(z = 260)
        captures = 0
        capture_list = []
        metadata_list = []
        processed_images = []
        sharpnesses = []
        capture_heights = []
        #TODO: This should probably also be an actual motor height
        max_stack_height = 47

        # So for testing a stack of 5 images, we need (5-1)/2=2 images before the peak
        # and 2 after the peak
        start_index = (stack_height - 1) / 2 
        failures = 0
        while captures < max_stack_height:
            capture_heights.append(stage.position['z'])
            img_array, img_metadata = capture_image(stage = stage)
            stage.move_relative(
                x = 0,
                y = 0,
                z = stack_dz
            )
            time.sleep(0.3)
            # processed_images.append(process_raw_image(rggb2rgb(raw2rggb(img_array))))
            processed_images.append(0)
            # _, frame = cv2.imencode('.JPEG', processed_images[-1])
            # sharpnesses.append(len(frame))
            sharpnesses.append(cam.grab_jpeg_size(stream_name="lores"))
            capture_list.append(img_array)
            metadata_list.append(img_metadata)
            captures += 1
            if len(sharpnesses) >= stack_height:
                result = self.test_sharpnesses(capture_heights[-stack_height:], sharpnesses[-stack_height:], logger, start_index, failures > -1)
                # logger.info(sharpnesses[-stack_height:])
                if result == 'success':
                    break
                elif np.argmax(sharpnesses[-stack_height:]) < start_index:
                    logger.info(f"Could't find focus. Gone too far. Peak was image {np.argmax(sharpnesses)}. List is {sharpnesses}")
                    stage.move_relative(x = 0, y = 0, z = -(500+max_stack_height*stack_dz))
                    # stage.move_relative(x = 0, y = 0, z = 200)
                    m = autofocus.move_and_measure(dz = [0,500+max_stack_height*stack_dz])
                    stage.move_relative(x = 0, y = 0, z = -(500+max_stack_height*stack_dz))
                    stage.move_relative(x = 0, y = 0, z = 100)
                    
                    _, heights, sizes = self.move_data(len(m.stage_positions)-2, data = m)
                    stage.move_absolute(
                        x = stage.position['x'],
                        y = stage.position['y'],
                        z = heights[np.argmax(sizes)] - undershoot*stack_dz
                        )
                    #NEED TO CLEAR THE LISTS AT THIS POINT!
                    processed_images = []
                    sharpnesses = []
                    capture_heights = []
                    capture_list = []
                    metadata_list = []
                    captures = 0
                    failures += 1
                elif captures == max_stack_height:
                    logger.info(f"Could't find focus. Took {len(sharpnesses)} images and the best one was at {np.argmax(sharpnesses)}. List is {sharpnesses}")
                    stage.move_absolute(z = capture_heights[np.argmax(sharpnesses)])
                    stage.move_relative(x = 0, y = 0, z = -(500+max_stack_height*stack_dz))
                    # stage.move_relative(x = 0, y = 0, z = 200)
                    m = autofocus.move_and_measure(dz = [0,500+max_stack_height*stack_dz])
                    stage.move_relative(x = 0, y = 0, z = -(500+max_stack_height*stack_dz))
                    stage.move_relative(x = 0, y = 0, z = 100)
                    
                    _, heights, sizes = self.move_data(len(m.stage_positions)-2, data = m)
                    stage.move_absolute(
                        x = stage.position['x'],
                        y = stage.position['y'],
                        z = heights[np.argmax(sizes)] - undershoot*stack_dz
                        )
                    #NEED TO CLEAR THE LISTS AT THIS POINT!
                    logger.debug(sharpnesses)
                    processed_images = []
                    sharpnesses = []
                    capture_heights = []
                    capture_list = []
                    metadata_list = []
                    captures = 0
                    failures += 1
                elif len(sharpnesses) > stack_height:
                    processed_images[-(stack_height+1)] = 0
                    sharpnesses[-(stack_height+1)] = 0
                    capture_heights[-(stack_height+1)] = 0
                    capture_list[-(stack_height+1)] = 0
                    metadata_list[-(stack_height+1)] = 0
        sharpest_index = np.argmax(sharpnesses)
        start_index = int(sharpest_index - (image_stack_height - 1) / 2)
        end_index = int(sharpest_index + (image_stack_height - 1) / 2)
        current_site_folder = f"{current_pos[0]}_{current_pos[1]}"
        if not os.path.isdir(os.path.join(images_folder, current_site_folder)):
            os.makedirs(os.path.join(images_folder, current_site_folder))
        if not os.path.isdir(os.path.join(images_folder, "use")):
            os.makedirs(os.path.join(images_folder, "use"))
        focused_image_name = os.path.join('use', f"{current_pos[0]}_{current_pos[1]}.jpeg")

        def save_captures():
            save_capture(focused_image_name, capture_list[sharpest_index], metadata_list[sharpest_index], current_pos, processed_images[sharpest_index])
            for i in range(start_index, end_index+1):
                save_capture(os.path.join(current_site_folder, f"{i}.jpeg"), capture_list[i], metadata_list[i], current_pos, processed_images[sharpest_index])
        save_thread = Thread(
            target = save_captures
        )
        return capture_heights[sharpest_index], save_thread
    @thing_property
    def stack_dz(self) -> int:
        """Space in steps between images in a z-stack
        Suggested is 50 for 60-100x
        100 for 40x
        200 for 20x"""
        return self.thing_settings.get("stack_dz", 10)
    
    @stack_dz.setter
    def stack_dz(self, value: int) -> None:
        self.thing_settings["stack_dz"] = value

    @thing_property
    def stack_test_height(self) -> int:
        """Number of images in the stack to test"""
        return self.thing_settings.get("stack_test_height", 9)
    
    @stack_test_height.setter
    def stack_test_height(self, value: int) -> None:
        self.thing_settings["stack_test_height"] = value

    @thing_property
    def stack_height(self) -> int:
        """The number of images to capture and save in a stack
        Defaults to 1 unless you need to see either side of focus"""
        return self.thing_settings.get("stack_height", 9)
    
    @stack_height.setter
    def stack_height(self, value: int) -> None:
        self.thing_settings["stack_height"] = value

    def test_sharpnesses(self, heights, sharpnesses, logger, start_index, accept_chevy = False):
        #TODO reimplement chebychev
        if np.argmax(sharpnesses) < start_index:
            return False
        if len(sharpnesses) - 1 - np.argmax(sharpnesses) < start_index:
            return False
        max_loc = np.argmax(sharpnesses)
        approach = sharpnesses[:max_loc+1]
        recede = sharpnesses[max_loc:]
        if sorted(approach) == approach and sorted(recede, reverse = True) == recede:
            logger.info('really good')
            logger.info(sharpnesses)
            return "success"
        elif accept_chevy:
            logger.info("testing cheby")
            dz = heights[1] - heights[0]
            centre_index = len(heights) // 2
            x = np.linspace(min(heights) - 1000, max(heights) + 1000, 1000)

            chevylevy = np.polynomial.chebyshev.chebfit(heights, sharpnesses, 4)
            sharpness_curve = cheb.chebval(x, chevylevy)

            der_chevy = cheb.chebder(chevylevy)
            dder_chevy = cheb.chebder(der_chevy)
            turning = cheb.chebroots(der_chevy)
            turning = turning[np.isreal(turning)]
            nature = np.asarray([np.real(cheb.chebval(point, dder_chevy)) for point in turning])
            maxima = turning[np.where(nature<0)]

            peak_height = ''
            
            if np.count_nonzero(np.logical_and(np.real(turning) >= heights[1], np.real(turning) <= heights[-2])) == 1:
                if np.count_nonzero(np.logical_and(maxima >= (heights[centre_index] - 1.5 * dz), maxima<=(heights[centre_index] + 1.5 * dz))) == 1:
                    for maximum in maxima:
                        if maximum >= heights[centre_index] - 1.5 * dz and maximum <= heights[centre_index] + 1.5 * dz:
                            peak_height = maximum
                            return "success"

        return False

    def move_data(
        self, istart: int, istop: Optional[int] = None, data: Optional[dict] = None
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract sharpness as a function of (interpolated) z"""
        if istop is None:
            istop = istart + 2
        try:
            jpeg_times: np.ndarray = np.array(data.jpeg_times)
        except:
            jpeg_times: np.ndarray = np.array(data['jpeg_times'])
        try:
            jpeg_sizes: np.ndarray = np.array(data.jpeg_sizes)
        except:
            jpeg_sizes: np.ndarray = np.array(data['jpeg_sizes'])
        try:
            stage_times: np.ndarray = np.array(data.stage_times)[
                istart:istop
            ]
        except:
            stage_times: np.ndarray = np.array(data['stage_times'])[
                istart:istop
            ]
        try:
            stage_positions: np.ndarray = np.array(data.stage_positions)
        except:
            stage_positions: np.ndarray = np.array(data['stage_positions'])

        stage_zs: np.ndarray = np.array(
            [p['z'] for p in stage_positions[istart:istop]]
          )
        try:
            start: int = int(np.argmax(jpeg_times > stage_times[0]))
            stop: int = int(np.argmax(jpeg_times > stage_times[1]))
        except ValueError as e:
            if np.sum(jpeg_times > stage_times[0]) == 0:
                raise ValueError(
                    "No images were captured during the move of the stage.  Perhaps the camera is not streaming images?"
                ) from e
            else:
                raise e
        if stop < 1:
            stop = len(jpeg_times)
            # logging.debug("changing stop to %s", (stop))
        jpeg_times = jpeg_times[start:stop]
        jpeg_zs: np.ndarray = np.interp(
            jpeg_times, stage_times, stage_zs
        )  # np.ndarray[float]
        return jpeg_times, jpeg_zs, jpeg_sizes[start:stop]
