import shutil
from typing import Mapping, Optional
import cv2
from fastapi import HTTPException
from fastapi.responses import FileResponse
import numpy as np
import os
import time
from PIL import Image
from pydantic import BaseModel
from scipy.stats import norm
import logging
from copy import deepcopy
from datetime import datetime

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.invocation import CancelHook, InvocationLogger, InvocationCancelledError
from labthings_fastapi.decorators import thing_action, thing_property, fastapi_endpoint
from labthings_sangaboard import SangaboardThing
from openflexure_microscope_server.interfaces.camera import AbstractCamera
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper
from openflexure_microscope_server.things.auto_recentre_stage import RecentringThing

StageDep = direct_thing_client_dependency(SangaboardThing, "/stage/")
CamDep = direct_thing_client_dependency(AbstractCamera, "/camera/")
CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")
RecentreStage = direct_thing_client_dependency(RecentringThing, "/auto_recentre_stage/")


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
    return np.max(np.divide(np.abs(np.subtract(current_loc, starting_loc)), step_size))

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

    camera_to_sample_matrix = scale_csm(camera_to_sample_matrix, csm_calibration_width, img_width)

    with open(os.path.join(folder_path, 'TileConfiguration.txt'), 'w') as fp:
        fp.write('# Define the number of dimensions we are working on\ndim = 2\n\n# Define the image coordinates\n')
        for i in range(len(names)):    
            loc = np.dot((positions[i] - mean_loc), np.linalg.inv(camera_to_sample_matrix))
            fp.write(f'{names[i]}; ; {loc[1], loc[0]} \n')

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
        return self.thing_settings.get("tolerance", 5)
    
    @tolerance.setter
    def tolerance(self, value: float) -> None:
        self.thing_settings["tolerance"] = value

    @thing_property
    def fraction(self) -> float:
        """How much of the image needs to be not background to label as sample"""
        return self.thing_settings.get("fraction", 7)

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


def ensure_free_disk_space(path: str, min_space: int = 500000000) -> None:
    """Raise an exception if we are running out of disk space"""
    du = shutil.disk_usage(path)
    if du.free < min_space:
        raise IOError(f"There is not enough free disk space to continue {du}")


class ScanInfo(BaseModel):
    """"Summary information about a scan folder"""
    name: str
    created: datetime
    modified: datetime
    number_of_images: int


DOWNLOADABLE_SCAN_FILES = (
    "images.zip",
)


class SmartScanThing(Thing):
    @property
    def scan_folder_path(self) -> str:
        """This folder will hold all the scans we do."""
        # TODO: This should be determined using sensible configuration.
        # If the working directory is `/var/openflexure` this will result
        # in scans being saved at `/var/openflexure/scans/`
        return "scans"
    
    def new_scan_folder(self) -> str:
        """Create a new empty folder, into which we can save scan images"""
        if not os.path.exists(self.scan_folder_path):
            os.makedirs(self.scan_folder_path)
        for j in range(999999):
            folder_path = os.path.join(self.scan_folder_path, f"scan_{j:06}")
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                return folder_path
        raise FileExistsError("Could not create a new scan folder: all names in use!")
    
    @thing_action
    def sample_scan(
        self,
        cancel: CancelHook,
        logger: InvocationLogger,
        autofocus: AutofocusDep,
        stage: StageDep,
        cam: CamDep,
        csm: CSMDep,
        background_detect: BackgroundDep,
        recentre: RecentreStage,
        sample_check
    ):
        """Move the stage to cover an area, taking images that can be tiled together.

        The stage will move in a pattern that grows outwards from the starting point,
        stopping once it is surrounded by "background" (as detected by the 
        background_detect Thing).

        Input:

        * `overlap` is the fraction by which images should overlap, i.e. 
          `0.3` means we will move by 70% of the field of view each time.
        """

        # Before anything else, check that we've got a background set
        # It's annoying to have to wait to find out!
        max_dist = self.max_range

        if sample_check:
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

        r = cam.grab_jpeg()
        arr = np.array(Image.open(r.open()))
        if list(arr.shape[:2]) != csm.image_resolution:
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
        
        # TODO: this downsampling by two is to deal with a camera issue
        img_width = int(arr.shape[1] / 2)

        overlap = self.overlap

        dx = int(np.dot(np.array([0, arr.shape[1] * (1 - overlap)]), CSM)[0])
        dy = int(np.dot(np.array([arr.shape[0] * (1 - overlap), 0]), CSM)[1])

        logger.info(f"Based on an overlap of {overlap}, we will make steps of {dx}, {dy}")

        # construct a 2D scan path
        path = [[stage.position["x"], stage.position["y"]]]

        focused_path = []  # This holds a list of all points where focus succeeded
        true_path = []  # This holds a list of all points visited
        i = 0
        ids = []
        start_time = time.strftime("%H_%M_%S-%d_%m_%Y")

        scan_path = self.new_scan_folder()
        images_folder = os.path.join(scan_path, "images")
        os.mkdir(images_folder)
        raw_images_folder = os.path.join(scan_path, "raw_images")
        os.mkdir(raw_images_folder)
        logger.info(f"Saving images to {images_folder}")

        try:
            # TODO: I think this is unnecessary, we do a looping autofocus at the first point in the loop, unless
            # it's flagged as background (which is a wierd case anyway)
            recentre.looping_autofocus()
            # move to each x-y position. in z, move to the height of the closest x-y position that successfully focused
            while len(path) > 0:

                loc = [path[0][0], path[0][1], stage.position["z"]]

                path.remove(path[0])

                # TODO: combine this with the move below for speed (I think this could just be "else")
                stage.move_absolute(x=int(loc[0]), y=int(loc[1]), z=int(loc[2]))

                if len(focused_path) > 1:
                    z_index = closest(loc, focused_path)
                    # print('Moving to {0}'.format([coords[0], coords[1], focused_path[z_index][2]]))
                    # print(focused_path)
                    stage.move_absolute(
                        x=int(loc[0]), y=int(loc[1]), z=int(focused_path[z_index][2])
                    )

                # Check if the image is background
                if sample_check:
                    image_is_sample = background_detect.image_is_sample()
                else:
                    image_is_sample = True

                # if more than 92% of the image is background, treat it as background and continue
                if not image_is_sample:
                    logger.info(f"Skipping {stage.position} as it is {round(background_detect.background_fraction(),0)}% background.")
                else:
                    # if not, it's sample. run an autofocus and use the updated height
                    new_pos = [
                        [stage.position["x"] - dx, stage.position["y"]],
                        [stage.position["x"] + dx, stage.position["y"]],
                        [stage.position["x"], stage.position["y"] - dy],
                        [stage.position["x"], stage.position["y"] + dy],
                    ]
                    for pos in new_pos:
                        if (
                            pos not in [sublist[:2] for sublist in true_path]
                            and pos not in path
                        ):
                            path.append(pos)

                    attempts = 0
                    while True:
                        recentre.looping_autofocus(dz=self.autofocus_dz)
                        current_height = stage.position["z"]

                        # if there have been successful autofocuses in this scan, find the closest one in x-y
                        # test if the change in z between them exceeds a ratio (indicating a failed autofocus)
                        if len(focused_path) > 0:
                            nearest_focused_site = focused_path[closest(loc, focused_path)]
                            result = limit_focus_change(
                                nearest_focused_site[0:2],
                                nearest_focused_site[-1],
                                loc[0:2],
                                current_height,
                                0.3,
                            )

                        # if there haven't been any previous autofocuses, we have to assume this one worked
                        else:
                            result = "accept"

                        # if the autofocus worked, add the current position to the list of successful locations
                        if result == "accept":
                            loc = list(stage.position.values())
                            focused_path.append(loc)
                            break
                        if attempts >= 5:
                            logger.warning("Could not autofocus after 5 attempts.")
                            break
                        # if the autofocus was rejected, we return to the height of the closest successful autofocus. not perfect, but better than wandering out of focus
                        logger.info(
                            "The focus seems to have moved farther than we expect. "
                            "We will now rest the Z position and try again. "
                            f"Options are {focused_path}, we chose "
                            f"{nearest_focused_site}"
                        )
                        stage.move_absolute(z=int(focused_path[z_index][2]))
                        attempts += 1

                    name = f"image_{loc[0]}_{loc[1]}.jpg"
                    # img = Image.open(cam.capture_jpeg(resolution="full").open())
                    jpegblob = cam.capture_jpeg(resolution="full")
                    jpegblob.save(os.path.join(raw_images_folder, name))
                    img = Image.open(jpegblob.open())
                    exif = img.info['exif']
                    width, height = img.size 
                    img = img.resize((int(width*0.5), int(height*0.5)))

                    logger.info(f"Saving {name} at {stage.position}")
                    img.save(
                        os.path.join(images_folder, name),
                        exif=exif,
                        quality=95,
                        subsampling=0
                    )
                    positions.append(loc[:2])
                    names.append(name)

                # add the current position to the list of all positions visited
                true_path.append(loc)

                if len(names) > 1:
                    generate_config(images_folder, positions, names, CSM, csm_calibration_width, img_width, logger)

                temp_path = []

                for i in path:
                    if distance_to_site(i, true_path[0][:2]) < max_dist:
                        temp_path.append(i)
                    else:
                        logger.info(f'Rejected moving to {i} as it is out of range')

                path = temp_path.copy()

                path = sorted(path, key=lambda x: (steps_from_centre(x, true_path[0][:2], dx, dy), distance_to_site(loc[:2], x)))

                if len(true_path) > 750:
                    break
        except InvocationCancelledError:
            logger.error("Stopping scan because it was cancelled.")
        except IOError as e:
            logger.exception(
                f"Stopping scan because of an IOError (most likely a full disk): {e}",
            )
        finally:
            logger.info("Creating zip archive of images (may take some time)...")
            shutil.make_archive(
                os.path.join(scan_path, "images"), "zip", images_folder
            )
            logger.info("Returning to starting position.")
            stage.move_absolute(**starting_position, block_cancellation=True)
    
    @thing_property
    def max_range(self) -> int:
        """The maximum distance from the centre of the scan before we break"""
        return self.thing_settings.get("max_range", 400000)

    @max_range.setter
    def max_range(self, value: int) -> None:
        self.thing_settings["max_range"] = value

    @thing_property
    def autofocus_dz(self) -> int:
        """The z distance to perform an autofocus"""
        return self.thing_settings.get("autofocus_dz", 3000)

    @autofocus_dz.setter
    def autofocus_dz(self, value: int) -> None:
        self.thing_settings["autofocus_dz"] = value

    @thing_property
    def overlap(self) -> float:
        """The z distance to perform an autofocus"""
        return self.thing_settings.get("overlap", 0.4)

    @overlap.setter
    def overlap(self, value: float) -> None:
        self.thing_settings["overlap"] = value

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
        for f in os.listdir(self.scan_folder_path):
            path = os.path.join(self.scan_folder_path, f)
            if os.path.isdir(path):
                images_folder = os.path.join(path, "images")
                if os.path.isdir(images_folder):
                    number_of_images = len(os.listdir(images_folder))
                else:
                    number_of_images = 0
                scans.append(
                    ScanInfo(
                        name = f,
                        created = os.path.getctime(path),
                        modified = os.path.getmtime(path),
                        number_of_images = number_of_images,
                    )
                )
        return scans
    
    @fastapi_endpoint(
            "get",
            "scans/{scan_name}/{file}",
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
        if file not in DOWNLOADABLE_SCAN_FILES:
            raise HTTPException(
                403, f"You may only download files named {DOWNLOADABLE_SCAN_FILES}"
            )
        path = os.path.join(self.scan_folder_path, scan_name, file)
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
        path = os.path.join(self.scan_folder_path, scan_name)
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