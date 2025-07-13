"""OpenFlexure Microscope API extension for stage calibration.

This file contains the HTTP API for camera/stage calibration. It
includes calibration functions that measure the relationship between
stage coordinates and camera coordinates, as well as functions that
move by a specified displacement in pixels, perform closed-loop moves,
and return the calibration data.

This module is only intended to be called from the OpenFlexure Microscope
server, and depends on that server and its underlying LabThings library.
"""

import time
from typing import (
    Any,
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
)
from fastapi import HTTPException

import numpy as np
from camera_stage_mapping.camera_stage_calibration_1d import (
    calibrate_backlash_1d,
    image_to_stage_displacement_from_1d,
)
from camera_stage_mapping.exceptions import MappingError

import labthings_fastapi as lt
from labthings_fastapi.types.numpy import DenumpifyingDict

from camera_stage_mapping.camera_stage_tracker import Tracker
from .camera import CameraDependency as Camera
from .stage import StageDependency as Stage

CoordinateType = Tuple[float, float, float]
XYCoordinateType = Tuple[float, float]


class MoveHistory(NamedTuple):
    """A named tuple containing the position over time for a single move.

    This a named tuple with elements:

    * ``times``
    * ``stage_positions``
    """

    times: List[float]
    stage_positions: List[CoordinateType]


class RecordedMove:
    """Call stage movement and maintain a record of position and time.

    This class is callable, the callable wraps stage.move_to_xyz_position.

    The class records a list of all moves made and how long they took. This is useful
    for calibrating the stage as it allows measuring how long moves take.
    """

    def __init__(self, stage: Stage):
        """Set the stage client used for for movement.

        :param stage: the stage client to be used. ``stage.move_to_xyz_position`` will
            be called whenever the instance is called.
        """
        self._stage: Stage = stage
        self._current_position: Optional[CoordinateType] = None
        self._history: List[Tuple[float, Optional[CoordinateType]]] = []

    def __call__(self, new_position: CoordinateType):
        """Move to a new position, and record it."""
        self._history.append((time.time(), self._current_position))
        self._stage.move_to_xyz_position(xyz_pos=new_position)
        self._current_position = new_position
        self._history.append((time.time(), self._current_position))

    @property
    def history(self) -> MoveHistory:
        """The history, as a numpy array of times and another of positions."""
        times: List[float] = [t for t, p in self._history if p is not None]
        positions: List[CoordinateType] = [p for t, p in self._history if p is not None]
        return MoveHistory(times, positions)

    def clear_history(self):
        """Reset our history to be an empty list."""
        self._history = []


class CSMUncalibratedError(HTTPException):
    """An HTTP Exception raised if camera stage mapping data is needed but unavailable.

    Camera Stage Mapping data is needed to convert from distances specified in fractions
    of the field of view to distances in motor steps. This is used when clicking on the
    live preview to move, or when performing a scan.
    """

    def __init__(self):
        """Customise the default error code and message of HTTPException."""
        HTTPException.__init__(
            self,
            503,
            (
                "The camera_stage_mapping calibration is not yet available. "
                "This probably means you need to run the calibration routine."
            ),
        )


class CameraStageMapper(lt.Thing):
    """A Thing to manage mapping between image and stage coordinates.

    To use this Thing, the stage must have axes named "x", "y", and "z", or must
    override the ``get_xyz_position()`` and ``move_to_xyz_position()`` methods.
    """

    @lt.thing_action
    def calibrate_1d(
        self,
        camera: Camera,
        stage: Stage,
        logger: lt.deps.InvocationLogger,
        direction: Tuple[float, float, float],
    ) -> DenumpifyingDict:
        """Move a microscope's stage in 1D, and figure out the relationship with the camera."""
        # Record positions and times for stage calibration
        recorded_move = RecordedMove(stage)
        tracker = Tracker(
            camera.capture_downsampled_array,
            stage.get_xyz_position,
            settle=camera.settle,
        )
        direction_array: np.ndarray = np.array(direction)

        starting_position = stage.position
        try:
            result: dict = calibrate_backlash_1d(
                tracker, recorded_move, direction_array, logger=logger
            )
        except lt.exceptions.InvocationCancelledError as e:
            logger.info("User cancelled the camera stage mapping calibration")
            logger.info("Returning to starting position")
            stage.move_absolute(**starting_position, block_cancellation=True)
            raise e
        except MappingError as e:
            logger.info("Returning to starting position due to failed calibration")
            stage.move_absolute(**starting_position, block_cancellation=True)
            raise e
        result["move_history"] = recorded_move.history
        result["image_resolution"] = camera.capture_downsampled_array().shape[:2]
        return result

    @lt.thing_action
    def calibrate_xy(
        self, camera: Camera, stage: Stage, logger: lt.deps.InvocationLogger
    ) -> DenumpifyingDict:
        """Move the microscope's stage in X and Y, to calibrate its relationship to the camera.

        This performs two 1d calibrations in x and y, then combines their results.
        """
        downsampling_factor = camera.downsampled_array_factor
        # Calibrate y-axis first as it is more likely to fail.
        # The x-y difference is due to the camera aspect ratio, not the stage hardware.
        logger.info("Calibrating Y axis:")
        cal_y: dict = self.calibrate_1d(camera, stage, logger, (0, 1, 0))
        logger.info("Calibrating X axis:")
        cal_x: dict = self.calibrate_1d(camera, stage, logger, (1, 0, 0))
        logger.info("Calibration complete, updating metadata.")

        # Combine X and Y calibrations to make a 2D calibration
        cal_xy: dict = image_to_stage_displacement_from_1d([cal_x, cal_y])
        # Correct the result for downsampling performed in the hardware interface
        # (this may be to speed up correlation, or to avoid debayering artifacts)
        cal_xy["image_to_stage_displacement"] /= downsampling_factor
        corrected_resolution = tuple(
            r * downsampling_factor for r in cal_x["image_resolution"]
        )

        csm_matrix = cal_xy["image_to_stage_displacement"]
        csm_as_string = (
            f"[{round(csm_matrix[0][0], 2)}, {round(csm_matrix[0][1], 2)},],"
            f"[{round(csm_matrix[1][0], 2)}, {round(csm_matrix[1][1], 2)}]"
        )
        logger.info(f"CSM matrix is {csm_as_string}.")

        data: Dict[str, dict] = {
            "camera_stage_mapping_calibration": cal_xy,
            "linear_calibration_x": cal_x,
            "linear_calibration_y": cal_y,
            "downsampled_image_resolution": cal_x["image_resolution"],
            "image_resolution": corrected_resolution,
            "downsampling": downsampling_factor,
        }

        self.last_calibration = DenumpifyingDict(data).model_dump()

        return data

    @lt.thing_property
    def image_to_stage_displacement_matrix(
        self,
    ) -> Optional[List[List[float]]]:  # 2x2 integer array
        """A 2x2 matrix that converts displacement in image coordinates to stage coordinates.

        Note that this matrix is defined using "matrix coordinates", i.e. image coordinates
        may be (y,x). This is an artifact of the way numpy, opencv, etc. define images. If
        you are making use of this matrix in your own code, you will need to take care of
        that conversion.

        It is often helpful to give a concrete example: to make a move in image coordinates
        (``dy``, ``dx``), where ``dx`` is horizontal, i.e. the longer dimension of the image, you
        should move the stage by:

        .. code-block:: python

            stage_disp = np.dot(
                np.array(image_to_stage_displacement_matrix),
                np.array([dy,dx]),
            )

        """
        if self.last_calibration is None:
            return None
        displacement_matrix = self.last_calibration["camera_stage_mapping_calibration"][
            "image_to_stage_displacement"
        ]
        return np.array(displacement_matrix).tolist()

    last_calibration = lt.ThingSetting(
        initial_value=None, model=Optional[dict], readonly=True
    )
    """The most recent CSM calibration."""

    @lt.thing_property
    def image_resolution(self) -> Optional[Tuple[float, float]]:
        """The image size used to calibrate the image_to_stage_displacement_matrix."""
        if self.last_calibration is None:
            return None
        return self.last_calibration["image_resolution"]

    def assert_calibrated(self):
        """Raise an exception if the image_to_stage_displacement matrix is not set."""
        if self.image_to_stage_displacement_matrix is None:
            # Disable check of no message in raised exception as the message is explicitly
            # added by CSMUncalibratedError
            raise CSMUncalibratedError()  # noqa: RSE102

    @lt.thing_action
    def move_in_image_coordinates(
        self,
        stage: Stage,
        x: float,
        y: float,
    ):
        """Move by a given number of pixels on the camera.

        NB x and y here refer to what is usually understood to be the horizontal and
        vertical axes of the image. In many toolkits, "matrix indices" are used, which
        swap the order of these coordinates. This includes opencv and PIL. So, don't be
        surprised if you find it necessary to swap x and y around.

        As a general rule, ``x`` usually corresponds to the longer dimension of the image,
        and ``y`` to the shorter one. Checking what shape your chosen toolkit reports for
        an image usually helps resolve any ambiguity.
        """
        self.assert_calibrated()
        relative_move: np.ndarray = np.dot(
            np.array([y, x]), np.array(self.image_to_stage_displacement_matrix)
        )
        stage.move_relative(x=relative_move[0], y=relative_move[1])

    @lt.thing_property
    def thing_state(self) -> dict[str, Any]:
        """Summary metadata describing the current state of the Thing."""
        return {
            k: getattr(self, k)
            for k in ["image_to_stage_displacement_matrix", "image_resolution"]
        }
