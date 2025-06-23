"""OpenFlexure Microscope autofocus module

This module defines a Thing that is responsible for using the stage and
camera together to perform an autofocus routine.

See repository root for licensing information.
"""

from __future__ import annotations
from contextlib import contextmanager
import logging
import time
from typing import Annotated, Mapping, Optional, Sequence
import os

from fastapi import Depends
import numpy as np
from pydantic import BaseModel, computed_field

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.blocking_portal import BlockingPortal
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.dependencies.metadata import GetThingStates
from labthings_fastapi.types.numpy import NDArray
from labthings_fastapi.dependencies.invocation import InvocationLogger

from .camera import RawCameraDependency as Camera
from .camera import CameraDependency as WrappedCamera
from .stage import StageDependency as Stage
from .capture import RawCaptureDependency as CaptureDep


class StackParams(BaseModel):
    """Pydantic model for scan parameters"""

    # These are generic settings that seem to apply well to a standard scan
    # and are not altered by default when running a scan

    # time (in seconds) between moving and capturing an image
    settling_time: float = 0.3
    # distance (in steps) to overshoot a move and then undo, to account for backlash
    backlash_correction: int = 250

    # how many times the minimum distance between images to include as a "nearby" image
    # default 1.4 includes images offset in x or y, but not diagonally
    neighbour_cutoff: float = 1.4

    # how many images can be appended to the stack after the predicted peak to test for focus
    # before assuming the focus was passed, and restarting the stack
    stack_height_limit: int = 15

    # how far below (in factors of stack_dz) the estimated optimal starting position to
    # begin the stack. Better to start slightly too low and require many images, rather than
    # too high and needing to autofocus and restart the stack
    img_undershoot: int = 5

    # These we expect to be overwritten by AutofocusThing properties
    stack_dz: int = 50
    images_to_capture: int = 1
    images_to_test: int = 5
    autofocus_dz: int = 2000

    # Per pydantic docs, even with the @property applied before @computed_field,
    # mypy may throw a Decorated property not supported error (mypy issue #1362)
    # To avoid this error message, add # type: ignore[prop-decorator] to the @computed_field line.

    @computed_field
    @property
    def stack_z_range(self) -> int:
        """The range of the entire z stack, in steps"""
        return self.stack_dz * (self.images_to_test - 1)

    @computed_field
    @property
    def steps_undershoot(self) -> int:
        """The distance to deliberately undershoot the estimated optimal starting point"""

        # Starting too low by "steps_undershoot" makes smart stacking faster.
        # Starting a stack too high requires it to move to the start,
        # autofocus and then re-stack. Starting slightly too low only
        # requires extra +z movements and captures.
        return self.stack_dz * self.img_undershoot


class JPEGSharpnessMonitor:
    __globals__ = globals()  # Required for FastAPI dependency

    def __init__(self, stage: Stage, camera: Camera, portal: BlockingPortal):
        self.camera = camera
        self.stage = stage
        self.portal = portal
        print(f"Created sharpness monitor with {stage}, {camera}, {portal}")
        self.stage_positions: list[Mapping[str, int]] = []
        self.stage_times: list[float] = []
        self.jpeg_times: list[float] = []
        self.jpeg_sizes: list[int] = []

    running = False

    async def monitor_sharpness(self):
        """Start monitoring the frame sizes"""
        self.running = True
        async for frame in self.camera.lores_mjpeg_stream.frame_async_generator():
            self.jpeg_times.append(time.time())
            self.jpeg_sizes.append(len(frame))
            if not self.running:
                break

    @contextmanager
    def run(self):
        """Context manager, during which we will monitor sharpness from the camera"""
        self.portal.start_task_soon(self.monitor_sharpness)
        try:
            yield
        finally:
            self.running = False

    def focus_rel(self, dz: int, **kwargs) -> tuple[int, int]:
        # Store the start time and position
        self.stage_times.append(time.time())
        self.stage_positions.append(self.stage.position)

        # Main move
        self.stage.move_relative(z=dz, **kwargs)

        # Store the end time and position
        self.stage_times.append(time.time())
        self.stage_positions.append(self.stage.position)

        # Index of the data for this movement
        data_index: int = len(self.stage_positions) - 2
        # Final z position after move
        final_z_position: int = self.stage_positions[-1]["z"]
        return data_index, final_z_position

    def move_data(
        self, istart: int, istop: Optional[int] = None
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract sharpness as a function of (interpolated) z"""
        if istop is None:
            istop = istart + 2
        jpeg_times: np.ndarray = np.array(self.jpeg_times)
        jpeg_sizes: np.ndarray = np.array(self.jpeg_sizes)
        stage_times: np.ndarray = np.array(self.stage_times)[istart:istop]
        stage_zs: np.ndarray = np.array(
            [p["z"] for p in self.stage_positions[istart:istop]]
        )
        try:
            start: int = int(np.argmax(jpeg_times > stage_times[0]))
            stop: int = int(np.argmax(jpeg_times > stage_times[1]))
        except ValueError as e:
            if np.sum(jpeg_times > stage_times[0]) == 0:
                errmsg = (
                    "No images were captured during the move of the stage. "
                    "Perhaps the camera is not streaming images?"
                )
                raise ValueError(errmsg) from e
            raise e
        if stop < 1:
            stop = len(jpeg_times)
            logging.debug("changing stop to %s", (stop))
        jpeg_times = jpeg_times[start:stop]
        jpeg_zs: np.ndarray = np.interp(
            jpeg_times, stage_times, stage_zs
        )  # np.ndarray[float]
        return jpeg_times, jpeg_zs, jpeg_sizes[start:stop]

    def sharpest_z_on_move(self, index: int) -> int:
        """Return the z position of the sharpest image on a given move"""
        _, jz, js = self.move_data(index)
        if len(js) == 0:
            raise ValueError(
                "No images were captured during the move of the stage.  Perhaps the camera is not streaming images?"
            )
        return jz[np.argmax(js)]

    def data_dict(self) -> SharpnessDataArrays:
        """Return the gathered data as a single convenient dictionary"""
        data = {}
        for k in ["jpeg_times", "jpeg_sizes", "stage_times", "stage_positions"]:
            data[k] = getattr(self, k)
        return SharpnessDataArrays(**data)


SharpnessMonitorDep = Annotated[JPEGSharpnessMonitor, Depends()]


class SharpnessDataArrays(BaseModel):
    jpeg_times: NDArray
    jpeg_sizes: NDArray
    stage_times: NDArray
    stage_positions: list[dict[str, int]]


class AutofocusThing(Thing):
    """The Thing concerned with combinations of z axis movements and the camera.

    Actions here involve moving a stage in z, and using the camera to either
    capture images (generally, z-stacking) and measuring the sharpness of the
    field of view to assess focus (autofocus and testing the success of a z-stack)"""

    @thing_action
    def fast_autofocus(
        self,
        sharpness_monitor: SharpnessMonitorDep,
        dz: int = 2000,
        start: str = "centre",
    ) -> SharpnessDataArrays:
        """Sweep the stage up and down, then move to the sharpest point

        This method will will move down by dz/2, sweep up by dz, and then evaluate
        the position where the image was sharpest. We'll then move back down, and
        finally up to the sharpest point.
        """
        with sharpness_monitor.run():
            # Move to (-dz / 2)
            if start == "centre":
                sharpness_monitor.focus_rel(-dz / 2)
            # Move to dz while monitoring sharpness
            # i: Sharpness monitor index for this move
            # z: Final z position after move
            i, z = sharpness_monitor.focus_rel(dz, block_cancellation=True)
            # Get the z position with highest sharpness from the previous move (index i)
            fz: int = sharpness_monitor.sharpest_z_on_move(i)
            # Move all the way to the start so it's consistent
            i, z = sharpness_monitor.focus_rel(-dz)
            # Move to the target position fz (relative move of (fz - z))
            sharpness_monitor.focus_rel(fz - z)
            # Return all focus data
            return sharpness_monitor.data_dict()

    @thing_action
    def z_move_and_measure_sharpness(
        self,
        sharpness_monitor: SharpnessMonitorDep,
        dz: Sequence[int],
        wait: float = 0,
    ) -> SharpnessDataArrays:
        """Make a move (or a series of moves) and monitor sharpness

        This method will will make a series of relative moves in z, and
        return the sharpness (JPEG size) vs time, along with timestamps
        for the moves. This can be used to calibrate autofocus.

        Each move is relative to the last one, i.e. we will finish at
        `sum(dz)` relative to the starting position.

        If `wait` is specified, we will wait for that many seconds
        between moves.
        """
        with sharpness_monitor.run():
            for i, current_dz in enumerate(dz):
                if i > 0 and wait > 0:
                    time.sleep(wait)
                sharpness_monitor.focus_rel(current_dz)
            return sharpness_monitor.data_dict()

    @thing_action
    def looping_autofocus(
        self,
        stage: Stage,
        sharpness_monitor: SharpnessMonitorDep,
        dz=2000,
        start="centre",
    ):
        """Repeatedly autofocus the stage until it looks focused.

        This action will run the `fast_autofocus` action until it settles on a point
        in the middle 3/5 of its range. Such logic can be helpful if the microscope
        is close to focus, but not quite within `dz/2`. It will attempt to autofocus
        up to 10 times.
        """
        repeat = True
        attempts = 0
        backlash = 200

        with sharpness_monitor.run():
            while repeat and attempts < 10:
                if start == "centre":
                    stage.move_relative(x=0, y=0, z=-(backlash + dz / 2))
                    stage.move_relative(x=0, y=0, z=backlash)

                i, z = sharpness_monitor.focus_rel(dz, block_cancellation=True)
                _, heights, sizes = sharpness_monitor.move_data(i)

                peak_height = heights[np.argmax(sizes)]
                height_min = np.min(heights)
                height_max = np.max(heights)

                if (
                    peak_height - height_min < dz / 5
                    or height_max - peak_height < dz / 5
                ):
                    attempts += 1
                    start = "centre"
                    stage.move_absolute(z=peak_height - backlash)
                    stage.move_absolute(z=peak_height)
                else:
                    repeat = False
                    stage.move_relative(x=0, y=0, z=-(dz + backlash))
                    stage.move_absolute(z=peak_height)
            return heights.tolist(), sizes.tolist()

    @thing_property
    def stack_images_to_capture(self) -> int:
        """The number of images to capture and save in a stack
        Defaults to 1 unless you need to see either side of focus"""
        return self.thing_settings.get("stack_images_to_capture", 1)

    @stack_images_to_capture.setter
    def stack_images_to_capture(self, value: int) -> None:
        self.thing_settings["stack_images_to_capture"] = value

    @thing_property
    def stack_images_to_test(self) -> int:
        """The number of images to test for successful focusing in a stack
        Defaults to 9, which balances reliability and speed"""
        return self.thing_settings.get("stack_images_to_test", 9)

    @stack_images_to_test.setter
    def stack_images_to_test(self, value: int) -> None:
        self.thing_settings["stack_images_to_test"] = value

    @thing_property
    def stack_dz(self) -> int:
        """Space in steps between images in a z-stack
        Suggested is 50 for 60-100x
        100 for 40x
        200 for 20x"""
        return self.thing_settings.get("stack_dz", 50)

    @stack_dz.setter
    def stack_dz(self, value: int) -> None:
        self.thing_settings["stack_dz"] = value

    @thing_action
    def run_smart_stack(
        self,
        cam: WrappedCamera,
        stage: Stage,
        logger: InvocationLogger,
        metadata_getter: GetThingStates,
        capture: CaptureDep,
        sharpness_monitor: SharpnessMonitorDep,
        images_dir: str,
        autofocus_dz: int,
    ) -> None:
        """Run a smart stack, which captures images offset in z, testing
        whether the sharpest image is towards the centre of the stack.
        The sharpest image, and optionally images around the sharpest,
        will be saved using their coordinates to images_dir

        Arguments:
        images_dir: the folder to save all images
        autofocus_dz: should the stack fail, the range to refocus over before retrying
        variables cam to sharpness_monitor are Thing dependencies injected automatically by LabThings FastAPI
        """

        # Set the variables to prevent changes from the GUI or other windows
        stack_parameters = StackParams(
            stack_dz=self.stack_dz,
            images_to_capture=self.stack_images_to_capture,
            images_to_test=self.stack_images_to_test,
            autofocus_dz=autofocus_dz,
        )

        # Ensure the stack settings are appropriate
        self.validate_stack_inputs(stack_parameters)

        success = False
        # Loop until a stack is successful
        while not success:
            result, heights, captures, sharpest_index = self.z_stack(
                images_dir,
                stack_parameters,
                stage,
                cam,
                capture,
                metadata_getter,
            )

            if result == "success":
                success = True
                break

            # If a stack is not successful, move to the start and autofocus
            self.reset_stack(
                heights,
                stack_parameters.autofocus_dz,
                stage,
                sharpness_monitor,
            )

        # Save the sharpest image, and images either side of focus
        self.save_stack(
            sharpest_index,
            captures,
            stack_parameters,
            logger,
            capture,
        )

        # Return the z position of the sharpest image, for path planning and tracking
        return heights[-stack_parameters.images_to_test :][sharpest_index]

    def reset_stack(
        self,
        heights: list[int],
        autofocus_dz: int,
        stage: Stage,
        sharpness_monitor: SharpnessMonitorDep,
    ) -> None:
        """Return to the initial height of the current stack, and run
        a looping autofocus. Clears all previous captures, heights and sharpnesses.

        Arguments:
        heights: a list of the z positions of previous captures
        autofocus_dz: the range in steps to autofocus
        variables stage and sharpness_monitor are Thing dependencies passed through from the calling action
        """
        stage.move_absolute(z=heights[0])
        self.looping_autofocus(
            stage=stage,
            sharpness_monitor=sharpness_monitor,
            dz=autofocus_dz,
        )

    def save_stack(
        self,
        sharpest_index: int,
        captures: list[list],
        stack_parameters: StackParams,
        logger: InvocationLogger,
        capture: CaptureDep,
    ) -> int:
        """Save the required captures to disk. Will save the sharpest image,
        and any images either side of focus.

        Arguments:
        sharpest_index: the index of the sharpest image, within the "images_to_test" slice
        captures: a list of captures, including file name, image data and metadata
        stack_parameters: a StackParams Pydantic model with stack settings
        variables logger and capture are Thing dependencies passed through from the calling action
        """
        # Find the range of images from the stack to capture
        stack_extent = int((stack_parameters.images_to_capture - 1) / 2)
        stack_range = range(
            sharpest_index - stack_extent, sharpest_index + stack_extent + 1
        )

        # Loop through the range, saving each capture to disk
        for capture_index in stack_range:
            capture._save_capture(
                jpeg_path=captures[-stack_parameters.images_to_test :][capture_index][
                    0
                ],
                image=captures[-stack_parameters.images_to_test :][capture_index][1],
                metadata=captures[-stack_parameters.images_to_test :][capture_index][2],
                logger=logger,
            )
        return sharpest_index

    def z_stack(
        self,
        images_dir: str,
        stack_parameters: StackParams,
        stage: Stage,
        cam: WrappedCamera,
        capture: CaptureDep,
        metadata_getter: GetThingStates,
    ) -> list:
        """Capture a series of images offset by stack_parameters.stack_dz, and test whether
        the sharpest image is towards the centre of the stack.

        Returns a test result string, a list of z positions, a list of captures and the
        index of the sharpest image in a successful stack.

        Arguments:
        images_dir: a string of the path to write all images
        stack_parameters: a StackParams Pydantic model with stack settings
        variables stage to metadata_getter are Thing dependencies passed through from the calling action
        """
        # Move down by the height of the z stack, plus an overshoot
        # Better to start too low and take too many images than too high and need to refocus
        stage.move_relative(
            z=-(
                stack_parameters.steps_undershoot
                + stack_parameters.backlash_correction
                + stack_parameters.stack_z_range / 2
            )
        )
        stage.move_relative(z=stack_parameters.backlash_correction)

        captures = []
        sharpnesses = []
        heights = []

        # If the sharpest image isn't found within the 15 images above the estimated point, break
        # the loop and return "restart"
        while len(captures) <= stack_parameters.images_to_test + 15:
            time.sleep(stack_parameters.settling_time)

            # Append a new image to the stack
            captures, heights, sharpnesses = self.capture_stack_image(
                captures,
                heights,
                sharpnesses,
                images_dir,
                cam,
                stage,
                capture,
                metadata_getter,
            )

            # If the number of images is enough to test, test them
            if len(captures) >= stack_parameters.images_to_test:
                stack_result = self.check_stack_result(
                    sharpnesses[-stack_parameters.images_to_test :]
                )

                if stack_result == "success":
                    sharpest_index = np.argmax(
                        sharpnesses[-stack_parameters.images_to_test :]
                    )
                    return "success", heights, captures, sharpest_index

                if stack_result == "restart":
                    return "restart", heights, None, None

            stage.move_relative(z=stack_parameters.stack_dz)
        return "restart", heights, None, None

    def capture_stack_image(
        self,
        captures: list[list],
        heights: list[int],
        sharpnesses: list[int],
        images_dir: str,
        cam: WrappedCamera,
        stage: Stage,
        capture: CaptureDep,
        metadata_getter: GetThingStates,
    ) -> list:
        """Append a new capture to the ongoing stack.
        Includes appending the height, image sharpness and image
        data to the relevant lists.

        arguments:
        captures: a list of captures, including file name, image data and metadata
        heights: a list of the z positions of previous captures
        sharpnesses: a list of the sharpnesses of previous captures
        images_dir: a path to the folder to save images
        variables stage to metadata_getter are Thing dependencies passed through from the calling action
        """
        stage_location = stage.position
        jpeg_path = os.path.join(
            images_dir,
            f"{stage_location['x']}_{stage_location['y']}_{stage_location['z']}.jpeg",
        )
        image, metadata = capture._capture_image(
            cam=cam,
            metadata_getter=metadata_getter,
        )
        captures.append([jpeg_path, image, metadata])
        sharpnesses.append(cam.grab_jpeg_size(stream_name="lores"))
        heights.append(stage_location["z"])

        return captures, heights, sharpnesses

    def validate_stack_inputs(self, stack_parameters) -> None:
        """Check the stack settings are appropriate, and raise an error if not

        Arguments:
        images_to_test: number of images in the stack to test for focus
        images_to_capture: number of images to be captured around the focused image
        """
        if stack_parameters.images_to_test < stack_parameters.images_to_capture:
            raise RuntimeError(
                "Can't capture more images than are tested. Please increase number to test, or decrease number to capture"
            )
        if stack_parameters.images_to_test % 2 == 0:
            raise RuntimeError("Images to test should be odd")
        if (
            stack_parameters.images_to_test <= 0
            or stack_parameters.images_to_capture <= 0
        ):
            raise RuntimeError("Stack parameters need to be at least 1")

    def check_stack_result(self, sharpnesses: list[int]) -> str:
        """Test a list of sharpnesses, to decide whether the sharpest image from a stack is within them

        Returns a string
        'success' if the sharpest image is towards the centre
        'continue' if the sharpest image is in the final two images of the list
        'restart' if the sharpest image is in the first two images of the list

        Arguments:
        sharpnesses: a list of the sharpnesses to test for focus
        """

        sharpest_index = np.argmax(sharpnesses)
        sharpness_length = len(sharpnesses)

        # If only testing one image, then by definition the sharpest is central
        if sharpness_length == 1:
            return "success"
        # If testing three images, test if the centre is the sharpest
        if sharpness_length == 3:
            if sharpest_index == 1:
                return "success"
            if sharpest_index == 0:
                return "restart"
            return "continue"

        # For larger stacks, test if the best image is not within two of the edge of the stack
        # ie for a stack of 7 images, best image must be between 3rd and and 5th
        exclusion_range = 2

        if sharpest_index < exclusion_range:
            return "restart"
        if sharpest_index >= sharpness_length - exclusion_range:
            return "continue"
        return "success"
