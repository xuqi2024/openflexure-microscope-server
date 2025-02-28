"""OpenFlexure Microscope autofocus module

This module defines a Thing that is responsible for using the stage and
camera together to perform an autofocus routine.

See repository root for licensing information.
"""

from __future__ import annotations
from contextlib import contextmanager
import time
from typing import Annotated, Mapping, Optional, Sequence

from fastapi import Depends

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.blocking_portal import BlockingPortal
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.types.numpy import NDArray
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.invocation import (
    InvocationLogger,
)
from .camera import RawCameraDependency as Camera
from .camera import CameraDependency as WrappedCamera
from .stage import StageDependency as Stage
from .settings_manager import SettingsManager
import numpy as np
from pydantic import BaseModel
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages 

Settings = direct_thing_client_dependency(SettingsManager, "/settings/")
### Autofocus utilities


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
        """Monitor focus while moving in z"""
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
        self, istart: int, istop: Optional[int] = None, logger = InvocationLogger, data: Optional[dict] = None
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
                raise ValueError(
                    "No images were captured during the move of the stage.  Perhaps the camera is not streaming images?"
                ) from e
            else:
                raise e
        if stop < 1:
            stop = len(jpeg_times)
        jpeg_times = jpeg_times[start:stop]
        jpeg_zs: np.ndarray = np.interp(
            jpeg_times, stage_times, stage_zs
        )
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
    def move_and_measure(
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
        self, stage: Stage, sharpness_monitor: SharpnessMonitorDep, dz=2000, start="centre"
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

    @thing_action
    def verify_focus_sharpness(
        self, sweep_sizes: list, camera: WrappedCamera, threshold: float = 0.95
    ):
        """Take the sharpness curve of the autofocus, and the size of the current frame
        to see if the autofocus completed successfully. Returns True if current sharpness
        is within "leniency" number of frames from the peak of the autofocus"""

        current_sharpness = camera.grab_jpeg_size(stream_name="lores")

        peak = np.max(sweep_sizes)
        base = np.min(sweep_sizes)
        cutoff = threshold * (peak - base)

        return current_sharpness >= base + cutoff

    @thing_action
    def autofocus_report(
        self,
        sharpness_monitor: SharpnessMonitorDep,
        stage: Stage,
        wrappedcamera: WrappedCamera,
        settings: Settings,
        logger: InvocationLogger,
        repeats: int = 20,
        plots: bool = True,
        notes: str = "None"
    ):
        """"Perform an autofocus calibration and optionally produce a PDF of results
        
        Repeatedly run autofocus, and test whether the resulting position
        is as sharp as expected and whether the stage has overshot.
        
        repeats: the number of autofocuses to run during the trial, default 20
        plots: whether to produce a PDF plotting results. bool, default True
        notes: any user notes to pass to the report, such as changes to the gears. default None."""

        # Looping autofocus to find a point that we can autofocus on reliably
        self.looping_autofocus(stage, sharpness_monitor)

        results, all_sweeps = self.run_sweeps(repeats, sharpness_monitor, logger)
        
        results['date_stamp'] = time.strftime("%Y-%m-%d")
        results['time_stamp'] =  time.strftime("%H_%M")
        results['hostname'] = settings.hostname

        if plots:
            self.plot_report(results, notes, all_sweeps)
        
        self.thing_settings["focus_data"] = results
        logger.info("Out of %s trials, it appears that %s overshot.", results['total'], results['overshot'])
        return results

    def plot_report(self, results, notes, all_sweeps):
        with PdfPages(f"logs/{results['date_stamp']}_{results['time_stamp']}_focus.pdf") as pdf:
            self.title_page(results, notes, pdf)
            self.plot_sweeps(results, all_sweeps, pdf)

    def plot_sweeps(self, results, all_sweeps, pdf):
        """Plot the sharpness against height of the autofocus measurement move and final move to peak"""
        # this is a histogram of results['fraction'] showing how often the result seems too low
        f, ax = plt.subplots(1,1)
        counts, bins = np.histogram(results['fraction'])
        plt.stairs(counts, bins)
        ax.set_xlabel('Result height over alignment sweep ratio (ideally 1)')
        pdf.savefig(f)
        plt.close(f)

        # this plots the data collection and alignment sweeps. ideally, they'll have the same form and peak
        for i in range(len(all_sweeps)):
            sweep_heights = all_sweeps[f'{i}'][2]['heights']
            sweep_sizes = all_sweeps[f'{i}'][2]['sizes']
            
            align_heights = all_sweeps[f'{i}'][6]['heights']
            align_sizes = all_sweeps[f'{i}'][6]['sizes']
            f,ax = plt.subplots(1,1)
            ax.plot(sweep_heights, sweep_sizes, '.', label = 'Collection step')
            ax.plot(align_heights, align_sizes, '.', label = 'Alignment step')
            ax.set_xlabel('z position (steps)')
            ax.set_ylabel('Filesize')
            plt.legend()
            pdf.savefig(f)
            plt.close(f)

    def title_page(self, results, notes, pdf):
        """Adds a title page to the plots pdf, with the microscope name, the time / date and any notes"""
        # this is a data / title page summarising the data
        f, ax = plt.subplots(1,1)
        ax.text(0.1, 0.8,f"""Autofocus test was run at {results['time_stamp']} on {results['date_stamp']}.
        Out of {results['total']} trials, it appears that {results['overshot']} overshot.
        User notes are {notes}.
        Microscope name is {results['hostname']}
        """,
        horizontalalignment='left',verticalalignment='center', transform=ax.transAxes, wrap=True)
        ax.axis('off')
        pdf.savefig(f)
        plt.close(f)
    
    def run_sweeps(self, repeats, sharpness_monitor, logger):
        """Collect the autofocus success data by running multiple autofocuses, and extracting the
        relevant move data. Interprets the relevant data by comparing the location and the height
        of the autofocus movements."""
        # Set up our results tracking
        results = {
            'overshot': 0,
            'fraction': [],
            'total': 0
        }

        all_sweeps = {}

        for i in range(repeats):
            # Get the data from the autofocus
            logger.info("Running autofocus %i out of %i", i+1, repeats)
            data = self.fast_autofocus(sharpness_monitor)

            all_sweeps[f'{i}'] = {}

            # There's 7 components to an autofocus dataset:
            # down, still, up, still, down, still, up to focus
            for starts in range(7):
                offset = len(data.stage_positions) - 8
                _, heights, sizes = sharpness_monitor.move_data(istart=starts+offset, data = data)       
                
                all_sweeps[f'{i}'][starts] = {}

                all_sweeps[f'{i}'][starts]['heights'] = heights
                all_sweeps[f'{i}'][starts]['sizes'] = sizes
            
            results['total'] += 1

            # the data collection is the 3rd in the list
            sweep_sizes = all_sweeps[f'{i}'][2]['sizes']
            
            # the aligning to peak step is the 7th
            align_sizes = all_sweeps[f'{i}'][6]['sizes']

            # peak is the sharpest from the collection step, base is the least show
            peak = np.max(sweep_sizes)
            base = np.min(sweep_sizes)
            sweep_range = (peak - base)

            # align result is the sharpness when the alignment ends
            align_result = align_sizes[-1]
            align_range = (align_result - base)
            
            # find the ratio between the highest sharpness from the collection step and the final sharpness
            results['fraction'].append(float(align_range / sweep_range))

            # check whether the sharpest image in the alignment step is where the autofocus ends
            if np.max(align_sizes) != align_result:
                results['overshot'] += 1
            
        return results, all_sweeps

    @thing_property
    def focus_data(self):
        """The results of the last calibration that was run"""
        return self.thing_settings.get("focus_data", None)