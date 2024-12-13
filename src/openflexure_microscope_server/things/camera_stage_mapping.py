"""
OpenFlexure Microscope API extension for stage calibration

This file contains the HTTP API for camera/stage calibration. It
includes calibration functions that measure the relationship between
stage coordinates and camera coordinates, as well as functions that
move by a specified displacement in pixels, perform closed-loop moves,
and return the calibration data.

This module is only intended to be called from the OpenFlexure Microscope
server, and depends on that server and its underlying LabThings library.
"""

import logging
import time
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
)
from fastapi import Depends, HTTPException

import numpy as np
from PIL import Image
from pydantic import BaseModel
from camera_stage_mapping.camera_stage_calibration_1d import (
    calibrate_backlash_1d,
    image_to_stage_displacement_from_1d,
)
from camera_stage_mapping.camera_stage_tracker import Tracker
import camera_stage_mapping.fft_image_tracking
from labthings_picamera2.thing import StreamingPiCamera2
from labthings_sangaboard import SangaboardThing
from openflexure_microscope_server.things.autofocus import AutofocusThing
import cv2
import math

from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.invocation import (
    InvocationCancelledError,
    InvocationLogger,
)
from labthings_fastapi.types.numpy import NDArray, denumpify, DenumpifyingDict
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.thing import Thing

Camera = direct_thing_client_dependency(StreamingPiCamera2, "/camera/")
Stage = direct_thing_client_dependency(SangaboardThing, "/stage/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")

CoordinateType = Tuple[float, float, float]
XYCoordinateType = Tuple[float, float]


class HardwareInterfaceModel(BaseModel):
    move: Callable[[NDArray], None]
    get_position: Callable[[], NDArray]
    grab_image: Callable[[], NDArray]
    settle: Callable[[], None]
    grab_image_downsampling: float = 1


def downsample(factor: int, image: np.ndarray) -> np.ndarray:
    """Downsample an image by taking the mean of each nxn region

    This should be very efficient: we calculate the mean of each
    `factor * factor` square, no interpolation. If the image is
    not an integer multiple of the resampling factor, we discard
    the left-over pixels. This avoids odd edge effects and keeps
    performance quick.
    """
    if factor == 1:
        return image
    new_size = [d // factor for d in image.shape[:2]]
    # First, we ensure we have something that's an integer multiple
    # of `factor`
    cropped = image[: new_size[0] * factor, : new_size[1] * factor, ...]
    reshaped = cropped.reshape(
        (new_size[0], factor, new_size[1], factor) + image.shape[2:]
    )
    return reshaped.mean(axis=(1, 3))


def make_hardware_interface(
    stage: Stage, camera: Camera, downsample_factor: int = 2
) -> HardwareInterfaceModel:
    """Construct the functions we need to interface with the hardware"""
    axes = stage.axis_names

    def pos2dict(pos: Sequence[float]) -> Mapping[str, float]:
        return {k: p for k, p in zip(axes, pos)}

    def dict2pos(posd: Mapping[str, float]) -> Sequence[float]:
        return tuple(posd[k] for k in axes if k in posd)

    def move(pos: CoordinateType) -> None:
        current_pos = stage.position
        new_pos = pos2dict(pos)
        displacement = {k: new_pos[k] - current_pos[k] for k in new_pos.keys()}
        stage.move_relative(**displacement)

    def get_position() -> CoordinateType:
        return dict2pos(stage.position)

    def grab_image() -> np.ndarray:
        img = camera.capture_array()
        return downsample(downsample_factor, img)

    def settle() -> None:
        time.sleep(0.2)
        camera.capture_metadata

    return HardwareInterfaceModel(
        move=move,
        get_position=get_position,
        grab_image=grab_image,
        settle=settle,
        grab_image_downsampling=downsample_factor,
    )


HardwareInterfaceDep = Annotated[
    HardwareInterfaceModel, Depends(make_hardware_interface)
]


class MoveHistory(NamedTuple):
    times: List[float]
    stage_positions: List[CoordinateType]


class LoggingMoveWrapper:
    """Wrap a move function, and maintain a log position/time.

    This class is callable, so it doesn't change the signature
    of the function it wraps - it just makes it possible to get
    a list of all the moves we've made, and how long they took.

    Said list is intended to be useful for calibrating the stage
    so we can estimate how long moves will take.
    """

    def __init__(self, move_function: Callable):
        self._move_function: Callable = move_function
        self._current_position: Optional[CoordinateType] = None
        self.clear_history()

    def __call__(self, new_position: CoordinateType, *args, **kwargs):
        """Move to a new position, and record it"""
        self._history.append((time.time(), self._current_position))
        self._move_function(new_position, *args, **kwargs)
        self._current_position = new_position
        self._history.append((time.time(), self._current_position))

    @property
    def history(self) -> MoveHistory:
        """The history, as a numpy array of times and another of positions"""
        times: List[float] = [t for t, p in self._history if p is not None]
        positions: List[CoordinateType] = [p for t, p in self._history if p is not None]
        return MoveHistory(times, positions)

    def clear_history(self):
        """Reset our history to be an empty list"""
        self._history: List[Tuple[float, Optional[CoordinateType]]] = []


class CSMUncalibratedError(HTTPException):
    def __init__(self):
        HTTPException.__init__(
            self,
            503,
            (
                "The camera_stage_mapping calibration is not yet available. "
                "This probably means you need to run the calibration routine."
            ),
        )


class InsufficientOverlapError(HTTPException):
    def __init__(self):
        HTTPException.__init__(
            self,
            503,
            (
                "The overlap you're requesting isn't enough to reliably align. "
                "Reduce the distance or split the move into multiple smaller moves."
            ),
        )


class CameraStageMapper(Thing):
    """A Thing to manage mapping between image and stage coordinates"""

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.thing_settings.write_to_file()

    @thing_action
    def calibrate_1d(
        self,
        hw: HardwareInterfaceDep,
        stage: Stage,
        logger: InvocationLogger,
        direction: Tuple[float, float, float],
    ) -> DenumpifyingDict:
        """Move a microscope's stage in 1D, and figure out the relationship with the camera"""
        move = LoggingMoveWrapper(
            hw.move
        )  # log positions and times for stage calibration
        tracker = Tracker(hw.grab_image, hw.get_position, settle=hw.settle)
        direction_array: np.ndarray = np.array(direction)

        starting_position = stage.position
        try:
            result: dict = calibrate_backlash_1d(
                tracker, move, direction_array, logger=logger
            )
        except InvocationCancelledError as e:
            logger.info("Returning to starting position")
            stage.move_absolute(**starting_position, block_cancellation=True)
            raise e
        except Exception as e:
            logger.info("Returning to starting position")
            stage.move_absolute(**starting_position, block_cancellation=True)
            raise e
        result["move_history"] = move.history
        result["image_resolution"] = hw.grab_image().shape[:2]
        return result

    @thing_action
    def calibrate_xy(
        self, hw: HardwareInterfaceDep, stage: Stage, logger: InvocationLogger
    ) -> DenumpifyingDict:
        """Move the microscope's stage in X and Y, to calibrate its relationship to the camera

        This performs two 1d calibrations in x and y, then combines their results.
        """
        logger.info("Calibrating X axis:")
        cal_x: dict = self.calibrate_1d(hw, stage, logger, (1, 0, 0))
        logger.info("Calibrating Y axis:")
        cal_y: dict = self.calibrate_1d(hw, stage, logger, (0, 1, 0))
        logger.info("Calibration complete, updating metadata.")

        # Combine X and Y calibrations to make a 2D calibration
        cal_xy: dict = image_to_stage_displacement_from_1d([cal_x, cal_y])
        # Correct the result for downsampling performed in the hardware interface
        # (this may be to speed up correlation, or to avoid debayering artifacts)
        cal_xy["image_to_stage_displacement"] /= hw.grab_image_downsampling
        corrected_resolution = tuple(
            r * hw.grab_image_downsampling for r in cal_x["image_resolution"]
        )
        self.thing_settings.update(denumpify(cal_xy))
        self.thing_settings["image_resolution"] = corrected_resolution

        csm_matrix = cal_xy["image_to_stage_displacement"]
        csm_as_string = f"[{round(csm_matrix[0][0], 2)}, {round(csm_matrix[0][1], 2)},],[{round(csm_matrix[1][0], 2)}, {round(csm_matrix[1][1], 2)}]"
        logger.info(f"CSM matrix is {csm_as_string}.")

        data: Dict[str, dict] = {
            "camera_stage_mapping_calibration": cal_xy,
            "linear_calibration_x": cal_x,
            "linear_calibration_y": cal_y,
            "downsampled_image_resolution": cal_x["image_resolution"],
            "image_resolution": corrected_resolution,
            "downsampling": hw.grab_image_downsampling,
        }

        self.thing_settings["last_calibration"] = DenumpifyingDict(data).model_dump()

        return data

    @thing_property
    def image_to_stage_displacement_matrix(
        self,
    ) -> Optional[List[List[float]]]:  # 2x2 integer array
        """A 2x2 matrix that converts displacement in image coordinates to stage coordinates.

        Note that this matrix is defined using "matrix coordinates", i.e. image coordinates
        may be (y,x). This is an artifact of the way numpy, opencv, etc. define images. If
        you are making use of this matrix in your own code, you will need to take care of
        that conversion.

        It is often helpful to give a concrete example: to make a move in image coordinates
        (`dy`, `dx`), where `dx` is horizontal, i.e. the longer dimension of the image, you
        should move the stage by:
        ```
        stage_disp = np.dot(
            np.array(image_to_stage_displacement_matrix),
            np.array([dy,dx]),
        )
        ```
        """
        displacement_matrix = self.thing_settings.get("image_to_stage_displacement")
        if not displacement_matrix:
            return None
        return np.array(displacement_matrix).tolist()

    @thing_property
    def image_resolution(self) -> Optional[Tuple[float, float]]:
        """The image size used to calibrate the image_to_stage_displacement_matrix"""
        return self.thing_settings.get("image_resolution", None)

    def assert_calibrated(self):
        """Raise an exception if the image_to_stage_displacement matrix is not set"""
        if self.image_to_stage_displacement_matrix is None:
            raise CSMUncalibratedError()

    @thing_property
    def last_calibration(self) -> Optional[Dict]:
        """The results of the last calibration that was run"""
        return self.thing_settings.get("last_calibration", None)

    @thing_action
    def move_in_image_coordinates(
        self,
        stage: Stage,
        x: float,
        y: float,
    ):
        """Move by a given number of pixels on the camera

        NB x and y here refer to what is usually understood to be the horizontal and
        vertical axes of the image. In many toolkits, "matrix indices" are used, which
        swap the order of these coordinates. This includes opencv and PIL. So, don't be
        surprised if you find it necessary to swap x and y around.

        As a general rule, `x` usually corresponds to the longer dimension of the image,
        and `y` to the shorter one. Checking what shape your chosen toolkit reports for
        an image usually helps resolve any ambiguity.
        """
        self.assert_calibrated()
        relative_move: np.ndarray = np.dot(
            np.array([y, x]), np.array(self.image_to_stage_displacement_matrix)
        )
        stage.move_relative(x=relative_move[0], y=relative_move[1])

    @thing_action
    def certify_move_in_image_coordinates(
        self,
        stage: Stage,
        cam: Camera,
        logger: InvocationLogger,
        x: float,
        y: float,
        threshold: int = 5,
    ):
        """Move by a given number of pixels on the camera and verify using cross correlation

        NB x and y here refer to what is usually understood to be the horizontal and
        vertical axes of the image. In many toolkits, "matrix indices" are used, which
        swap the order of these coordinates. This includes opencv and PIL. So, don't be
        surprised if you find it necessary to swap x and y around.

        As a general rule, `x` usually corresponds to the longer dimension of the image,
        and `y` to the shorter one. Checking what shape your chosen toolkit reports for
        an image usually helps resolve any ambiguity.

        The move it attempts will try to undershoot by 5% of move - it's easier to keep moving
        than to turn around. Once it gets within "threshold" pixels of the target position, it'll
        break. Currently doesn't do anything useful if it overshoots, just logs the problem but
        stays there.
        """
        self.assert_calibrated()

        # TODO limit move to one FOV
        # TODO make sure this doesn't go crazy!
        if np.abs(x) > cam.stream_resolution[0] or np.abs(y) > cam.stream_resolution[1]:
            raise InsufficientOverlapError()
        if (
            np.abs(x) > cam.stream_resolution[0] * 0.8
            or np.abs(y) > cam.stream_resolution[1] * 0.8
        ):
            logger.warning(
                "The overlap is likely to be too small for this to be reliable"
            )

        resize = 0.5
        undershoot = 0.8
        image_0 = Image.open(cam.grab_jpeg().open())

        starting_pos = stage.position

        y_move = y
        x_move = x
        attempts = 0
        while attempts < 5 and [x_move, y_move] != [0, 0]:
            logger.debug(f"Trying to move by {x_move} {y_move}")
            relative_move: np.ndarray = np.dot(
                np.array([y_move, x_move]),
                np.array(self.image_to_stage_displacement_matrix),
            )

            stage.move_relative(
                x=int(relative_move[0] * undershoot),
                y=int(relative_move[1] * undershoot),
            )
            image_1 = Image.open(cam.grab_jpeg().open())

            offset = [
                int(i / resize)
                for i in self.get_displacement_between_images(
                    image_1, image_0, resize=resize
                )
            ][::-1]

            logger.debug(f"Measured offset is {offset}")

            if np.all(np.abs(np.subtract(offset, [x, y])) < threshold):
                # logger.info('Good move')
                break
            # TODO: safe divide to avoid div/0
            elif (
                np.any(np.abs(offset / np.array([x, y])) < 0.02)
                or np.any(offset > np.max(np.array([[x, 30], [y, 30]])) * 1.3)
                or np.any(np.subtract(np.abs(offset), np.abs(np.array([x, y]))) > 20)
            ):
                logger.debug("Correlation didn't look good, retrying")
                stage.move_relative(
                    x=int(-relative_move[0] * undershoot),
                    y=int(-relative_move[1] * undershoot),
                )
                attempts += 1
                if attempts >= 5:
                    logger.warning("Closed loop move didn't look successful")
                    stage.move_absolute(x=starting_pos["x"], y=starting_pos["y"])
                    relative_move: np.ndarray = np.dot(
                        np.array([y, x]),
                        np.array(self.image_to_stage_displacement_matrix),
                    )
                    stage.move_relative(
                        x=int(relative_move[0] + math.copysign(40, relative_move[0])),
                        y=int(relative_move[1] + math.copysign(40, relative_move[1])),
                    )
                    break
                undershoot *= 0.95
            else:
                x_move = x - offset[0]
                y_move = y - offset[1]

                # logger.info(f'Missed in x by {x_move}')
                # logger.info(f'Missed in y by {y_move}')

                if x_move / (x + 0.0001) < 0:  # or np.abs(offset[0] - x) < threshold:
                    x_move = 0
                if y_move / (y + 0.0001) < 0:  # or np.abs(offset[1] - y) < threshold:
                    y_move = 0
                if np.abs(x_move) < threshold and np.abs(y_move) < threshold:
                    x_move = 0
                    y_move = 0
                undershoot *= 0.95
                if attempts >= 5:
                    logger.warning("Closed loop move didn't look successful")
                    break

    @thing_action
    def split_certified_move_in_image_coordinates(
        self, stage: Stage, cam: Camera, autofocus: AutofocusDep, x: float, y: float
    ):
        """Move by a given number of pixels on the camera and verify using cross correlation

        NB x and y here refer to what is usually understood to be the horizontal and
        vertical axes of the image. In many toolkits, "matrix indices" are used, which
        swap the order of these coordinates. This includes opencv and PIL. So, don't be
        surprised if you find it necessary to swap x and y around.

        As a general rule, `x` usually corresponds to the longer dimension of the image,
        and `y` to the shorter one. Checking what shape your chosen toolkit reports for
        an image usually helps resolve any ambiguity.

        The move it attempts will try to undershoot by 5% of move - it's easier to keep moving
        than to turn around. Once it gets within "threshold" pixels of the target position, it'll
        break. Currently doesn't do anything useful if it overshoots, just logs the problem but
        stays there.
        """
        self.assert_calibrated()

        stream_resolution = cam.stream_resolution

        # TODO limit move to one FOV
        x_count = np.abs(np.floor(x / (0.5 * stream_resolution[0])))
        x_remainder = x % x_count

        y_count = np.abs(np.floor(y / (0.5 * stream_resolution[1])))
        y_remainder = y % y_count

        logging.info(
            f"We're wanting to move {x}, {y}. Splitting it into moving by half the FOV {x_count}, {y_count} times, then an extra {x_remainder}, {y_remainder}"
        )
        for i in range(int(x_count)):
            self.certify_move_in_image_coordinates(
                stage, cam, 0.5 * stream_resolution[0], 0
            )
            if i % 3 == 2:
                autofocus.looping_autofocus()
        for i in range(int(y_count)):
            self.certify_move_in_image_coordinates(
                stage, cam, 0, 0.5 * stream_resolution[1]
            )
            if i % 3 == 2:
                autofocus.looping_autofocus()

        self.certify_move_in_image_coordinates(stage, cam, x_remainder, 0)
        self.certify_move_in_image_coordinates(stage, cam, 0, y_remainder)

    @thing_property
    def thing_state(self) -> dict[str, Any]:
        """Summary metadata describing the current state of the Thing"""
        return {
            k: getattr(self, k)
            for k in ["image_to_stage_displacement_matrix", "image_resolution"]
        }

    @thing_action
    def get_displacement_between_images(
        self, image_0, image_1, sigma=10, fractional_threshold=0.1, pad=True, resize=0.1
    ):
        image_0 = cv2.resize(np.array(image_0), dsize=(0, 0), fx=resize, fy=resize)
        image_1 = cv2.resize(np.array(image_1), dsize=(0, 0), fx=resize, fy=resize)
        return camera_stage_mapping.fft_image_tracking.displacement_between_images(
            image_0=image_0,
            image_1=image_1,
            sigma=10,
            fractional_threshold=0.1,
            pad=True,
        ).tolist()
