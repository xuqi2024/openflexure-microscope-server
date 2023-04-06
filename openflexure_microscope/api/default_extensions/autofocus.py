import inspect
import logging
import time
from contextlib import contextmanager
from typing import Callable, Dict, List, Optional, Tuple, cast

import numpy as np
from labthings import current_action, fields, find_component
from labthings.extensions import BaseExtension
from labthings.utilities import get_docstring, get_summary
from labthings.views import ActionView, View
from scipy import ndimage

from openflexure_microscope.camera.base import BaseCamera
from openflexure_microscope.devel import abort
from openflexure_microscope.microscope import Microscope
from openflexure_microscope.stage.base import BaseStage
from openflexure_microscope.utilities import set_properties

### Autofocus utilities


class JPEGSharpnessMonitor:
    """Monitor JPEG frame size in a background thread
    
    This class starts a background thread """

    def __init__(self, microscope: Microscope):
        self.microscope: Microscope = microscope
        self.camera: BaseCamera = microscope.camera
        self.stage: BaseStage = microscope.stage

        self.recording_start_time: Optional[float] = None

        self.stage_positions: List[Tuple[int, int, int]] = []
        self.stage_times: List[float] = []
        self.jpeg_times: List[float] = []
        self.jpeg_sizes: List[int] = []

    def start(self):
        # Log the recording start time
        self.recording_start_time = time.time()

    def stop(self):
        self.camera.stream.stop_tracking()
        self.camera.stream.reset_tracking()

    def hold(self, delay: int = 5):
        """Run time.sleep for delay seconds, 
        while monitoring the JPEG frame size of the stream"""
        self.camera.stream.start_tracking()
        self.stage_times.append(time.time())
        self.stage_positions.append(self.stage.position)

        time.sleep(delay)

        self.camera.stream.stop_tracking()
        self.stage_times.append(time.time())
        self.stage_positions.append(self.stage.position)

        # Retrieve frame data
        for frame in self.camera.stream.frames:
            # Make timestamp absolute Unix time
            self.jpeg_times.append(frame.time)
            self.jpeg_sizes.append(frame.size)
        # Clear frame data for this move from the stream
        self.camera.stream.reset_tracking()

        # Index of the data for this movement
        data_index: int = len(self.stage_positions) - 2
        # Final z position after move
        final_z_position: int = self.stage_positions[-1][2]
        return data_index, final_z_position

    def focus_rel(self, dz: int, backlash: bool = False, **kwargs) -> Tuple[int, int]:
        # Store the start time and position
        self.camera.stream.start_tracking()
        self.stage_times.append(time.time())
        self.stage_positions.append(self.stage.position)

        # Main move
        self.stage.move_rel((0, 0, dz), backlash=backlash, **kwargs)

        # Store the end time and position
        self.camera.stream.stop_tracking()
        self.stage_times.append(time.time())
        self.stage_positions.append(self.stage.position)

        # Retrieve frame data
        for frame in self.camera.stream.frames:
            # Make timestamp absolute Unix time
            self.jpeg_times.append(frame.time)
            self.jpeg_sizes.append(frame.size)
        # Clear frame data for this move from the stream
        self.camera.stream.reset_tracking()

        # Index of the data for this movement
        data_index: int = len(self.stage_positions) - 2
        # Final z position after move
        final_z_position: int = self.stage_positions[-1][2]
        return data_index, final_z_position

    def move_data(
        self, istart: int, istop: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract sharpness as a function of (interpolated) z"""
        if istop is None:
            istop = istart + 2
        jpeg_times: np.ndarray = np.array(self.jpeg_times)  # np.ndarray[float]
        jpeg_sizes: np.ndarray = np.array(self.jpeg_sizes)  # np.ndarray[int]
        stage_times: np.ndarray = np.array(self.stage_times)[
            istart:istop
        ]  # np.ndarray[float]
        stage_zs: np.ndarray = np.array(self.stage_positions)[
            istart:istop, 2
        ]  # np.ndarray[int]
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

    def data_dict(self) -> Dict[str, np.ndarray]:
        """Return the gathered data as a single convenient dictionary"""
        data = {}
        for k in ["jpeg_times", "jpeg_sizes", "stage_times", "stage_positions"]:
            data[k] = getattr(self, k)
        return data


@contextmanager
def monitor_sharpness(microscope: Microscope):
    m: JPEGSharpnessMonitor = JPEGSharpnessMonitor(microscope)
    m.start()
    try:
        yield m
    finally:
        m.stop()


def sharpness_sum_lap2(rgb_image: np.ndarray) -> float:
    """Return an image sharpness metric: sum(laplacian(image)**")"""
    image_bw = np.mean(rgb_image, 2)
    image_lap = ndimage.filters.laplace(image_bw)
    return float(np.mean(image_lap.astype(float) ** 4))


def sharpness_edge(image: np.ndarray) -> float:
    """Return a sharpness metric optimised for vertical lines"""
    gray = np.mean(image.astype(float), 2)
    n: int = 20
    edge: np.ndarray = np.array([[-1] * n + [1] * n])
    return float(
        np.sum([np.sum(ndimage.filters.convolve(gray, W) ** 2) for W in [edge, edge.T]])
    )


def find_microscope() -> Microscope:
    """Find the microscope component or raise an exception.
    
    This function will fail with HTTPError extensions if it can't 
    find the appropriate hardware.

    We return a `Microscope` object
    """
    microscope = find_component("org.openflexure.microscope")

    if not microscope:
        abort(503, "No microscope connected. Unable to autofocus.")

    return microscope


def find_microscope_with_real_stage() -> Microscope:
    """Find the microscope and ensure it has a real stage.
    
    This function wraps `find_microscope()` and additionally asserts
    that there is a real stage, raising a `503` code if not.
    """
    microscope = find_microscope()

    if not microscope.has_real_stage():
        abort(503, "No stage connected. Unable to autofocus.")

    return microscope


def extension_action(args=None):
    """A decorator to auto-create an Action endpoint for a method
    
    Use this decorator on any method of an extension (`BaseExtension` subclass)
    and it will automatically be added to the API.  At present it is deliberately
    basic, and the plan is to expand the options in the future.
    
    Currently, you may specify `args` (which is a Marshmallow-format schema
    or dictionary, determining the datatype of the arguments, which will be
    taken from the JSON payload of the POST request initiating the action).
    
    The parsed arguments dictionary is expanded as the function arguments,
    i.e. we call `decorated_method(self, **kwargs)`.  This means that any
    unused arguments will cause an error, which is probably good practice...

    NB this decorator does **not** replace the function with a `View` or 
    register it with the parent `Extension`.  It adds the created `View` as 
    a property of the function, `flask_view`.  The parent `Extension` is
    responsible for collating and adding the views in its `__init__` method.
    """
    supplied_args = args

    def decorator(func):
        class_docstring = f"""Manage actions for {func.__name__}.
        
        This `View` class will return a list of `Action` objects representing
        each time {func.__name__} has been run in response to a `GET` request,
        and will start a new `Action` in response to a `POST` request.
        """

        class ActionViewWrapper(ActionView):
            __doc__ = class_docstring
            args = supplied_args

            def post(self, arguments):
                # Run the action
                return func(self.extension, **arguments)

            def get(
                self, *args, **kwargs
            ):  # pylint: disable=useless-super-delegation,arguments-differ
                # Explicitly wrap the `get` method to allow us to add a docstring
                return super().get(*args, **kwargs)

        # Create a nice docstring.  NB because the source function and this docstring
        # aren't guaranteed to have the same leading whitespace, we just make sure
        # both docstrings are stripped of leading indent, using `inspect.cleandoc()`
        ActionViewWrapper.post.description = (
            get_docstring(func, remove_newlines=False)
            + "\n\n"
            + inspect.cleandoc(
                """
                This `POST` request starts an Action, i.e. the hardware will do something
                that may continue after the HTTP request has been responded to.  The 
                response will always be an Action object, that details the current 
                status of the action and provides an interface to poll for completion.
                
                If the action completes within a specified timeout, we will return
                an HTTP status code of `200` and the return value will include any
                output from the action.  If it does not complete, we will return a
                `201` response code, and the action's endpoint may be polled to follow
                its progress.
                """
            )
        )
        ActionViewWrapper.post.summary = get_summary(func)
        ActionViewWrapper.post.__doc__ = ActionViewWrapper.post.description
        ActionViewWrapper.__name__ = func.__name__
        ActionViewWrapper.get.summary = (
            f"List running and completed `{func.__name__}` actions."
        )
        ActionViewWrapper.get.description = (
            ActionViewWrapper.get.summary
            + "\n\n"
            + inspect.cleandoc(
                f"""
                This `GET` request will return a list of `Action` objects corresponding
                to the `{func.__name__}` action.  It will include all the times it has
                been run since the server was last restarted, including running, completed,
                and failed attempts.
                """
            )
        )

        func.flask_view = ActionViewWrapper
        return func

    return decorator


### Autofocus extension


class AutofocusExtension(BaseExtension):
    def __init__(self):
        super().__init__(
            "org.openflexure.autofocus",
            version="2.0.0",
            description="Actions to move the microscope in Z and pick the point with the sharpest image.",
        )
        self.add_view(
            MeasureSharpnessAPI, "/measure_sharpness", endpoint="measure_sharpness"
        )
        self.add_decorated_method_views()

    def add_decorated_method_views(self):
        """Add views from any methods that have been decorated
        
        Using the decorators `@extension_action()` et al will add a
        property to the decorated method, `method_view`.  If this is
        present, this function will add the views to the extension.
        """
        for k in dir(self):
            obj = getattr(self, k)
            if hasattr(obj, "flask_view"):
                name = obj.__name__
                self.add_view(obj.flask_view, f"/{name}", endpoint=name)

    def measure_sharpness(
        self,
        microscope: Optional[Microscope] = None,
        metric_fn: Callable = sharpness_sum_lap2,
    ) -> float:
        """Measure the sharpness from the MJPEG stream
        
        Take a JPEG snapshot from the camera (extracted from the live preview stream)
        and return its size.  This is the sharpness metric used by the fast autofocus
        method.
        """
        if not microscope:
            microscope = find_microscope()
        if hasattr(microscope.camera, "array") and callable(
            getattr(microscope.camera, "array")
        ):
            return metric_fn(getattr(microscope.camera, "array")(use_video_port=True))
        else:
            raise RuntimeError(f"Object {microscope.camera} has no method `array`")

    @extension_action(
        args={
            "dz": fields.List(
                fields.Int(),
                metadata={
                    "description": "An ascending list of relative z positions",
                    "example": [int(x) for x in np.linspace(-300, 300, 7)],
                },
            )
        }
    )
    def autofocus(
        self,
        microscope: Optional[Microscope] = None,
        dz: Optional[List[int]] = None,
        settle: float = 0.5,
        metric_fn: Callable = sharpness_sum_lap2,
    ) -> Tuple[List[int], List[float]]:
        """Perform a simple autofocus routine.

        The stage is moved to z positions (relative to current position) in dz,
        and at each position an image is captured and the sharpness function 
        evaulated.  We then move back to the position where the sharpness was
        highest.  No interpolation is performed.

        dz is assumed to be in ascending order (starting at -ve values)
        """
        if not microscope:
            microscope = find_microscope_with_real_stage()
        camera: BaseCamera = microscope.camera
        stage: BaseStage = microscope.stage
        if not dz:
            dz = list(np.linspace(-300, 300, 7))
        dz = cast(List[int], dz)  # dz can't now be None, so fix its type.

        with set_properties(stage, backlash=256), stage.lock, camera.lock:
            sharpnesses: List[float] = []
            positions: List[int] = []

            # Some cameras may not have annotate_text. Reset if it does
            if getattr(camera, "annotate_text", None):
                setattr(camera, "annotate_text", "")

            for _ in stage.scan_z(dz, return_to_start=False):
                if current_action() and current_action().stopped:
                    return [], []
                positions.append(stage.position[2])
                time.sleep(settle)
                sharpnesses.append(self.measure_sharpness(microscope, metric_fn))

            newposition: int = positions[int(np.argmax(sharpnesses))]
            stage.move_rel((0, 0, newposition - stage.position[2]))

        return positions, sharpnesses

    def move_and_find_focus(
        self, microscope: Optional[Microscope] = None, dz: int = 0
    ) -> int:
        """Make a relative Z move and return the peak sharpness position"""
        if not microscope:
            microscope = find_microscope_with_real_stage()
        with monitor_sharpness(microscope) as m:
            m.focus_rel(dz)
            return m.sharpest_z_on_move(0)

    @extension_action(
        args={
            "dz": fields.Int(
                required=True, metadata={"description": "The relative Z move to make"}
            )
        }
    )
    def move_and_measure(
        self, microscope: Optional[Microscope] = None, dz: int = 0
    ) -> Dict[str, np.ndarray]:
        """Make a relative move in Z and measure dynamic sharpness

        This accesses the underlying method used by the fast autofocus routines, to
        move the stage while monitoring the sharpness, as reported by the size of
        each JPEG frame in the preview stream.  It returns a dictionary with
        stage position vs time and image size (i.e. sharpness) vs time.
        """
        if not microscope:
            microscope = find_microscope_with_real_stage()
        with monitor_sharpness(microscope) as m:
            m.focus_rel(dz)
            return m.data_dict()

    @extension_action(
        args={
            "dz": fields.Int(
                load_default=2000,
                metadata={
                    "description": "Total Z range to search over (in stage steps)",
                    "example": 2000,
                },
            )
        }
    )
    def fast_autofocus(
        self, microscope: Optional[Microscope] = None, dz: int = 2000
    ) -> Dict[str, np.ndarray]:
        """Perform a fast down-up-down-up autofocus
        
        This "fast" autofocus method moves the stage continuously in Z, while
        following the sharpness using the MJPEG stream.  This version is the
        simplest "fast" autofocus method, and performs the following sequence 
        of moves:

        1. Move to `-dz/2`, i.e. the bottom of the range
        2. Move up by `dz`, i.e. to the top of the range, while recording the
           sharpness of the image as a function of time.  Record the estimated
           position of the stage when the sharpness was maximised, `fz`.
        3. Move back to the bottom (by `-dz`)
        4. Move up to the position where it was sharpest.

        ## Backlash correction
        This routine should cancel out backlash: the stage is moving upwards as
        we record the sharpnes vs z data, and it is also moving upwards when
        we make the final move to the sharpest point.  Mechanical backlash should
        therefore be the same in both cases.

        This does not account for lag between the sharpness measurements and the
        stage's motion; that has been tested for and seems not to be a big issue
        most of the time, but may need to be accounted for in the future, if
        hardware or software changes increase the latency.

        ## Sharpness metric
        This method uses the MJPEG preview stream to estimate the sharpness of
        the image.  MJPEG streams consist of a series of independent JPEG images,
        so each frame can be looked at in isolation (though see later for an 
        important caveat).  JPEG images are compressed lossily, by taking the 
        discrete cosine transform (DCT) of each 8x8 block in the image.  A very
        rough precis of how this works is that after the DCT, cosine components 
        that are deemed unimportant (i.e. smaller than a threshold) are discarded.
        The effect is that images with lots of high-frequency information have a
        larger file size.

        We look only at the size of each JPEG frame in the stream, so we get a
        remarkably robust estimate of image sharpness without even opening the 
        images!  That's what lets us analyse 30 images/second even on the very
        limited processing power available to the Raspberry Pi 3.

        ## Warning: frame independence
        We assume that JPEG frames are independent.  This is only true if the
        MJPEG stream is encoded at *constant quality* without any additional
        bit rate control.  By default, many streams will reduce the quality
        factor if they exceed a target bit rate, which badly affects this
        method.  We turn off bit rate limiting for the Raspberry Pi camera,
        which fixes the problem, at the expense of sometimes failing if
        particularly sharp images appear in the stream, as there is a fairly
        small maximum size for each JPEG frame beyond which empty images are 
        returned.

        ## Estimation of sharpness vs z
        What we record during an autofocus is two time series, from two parallel
        threads.  One thread monitors the camera, and records the size of each
        JPEG frame as a function of time.  NB this is time from `time.time()`
        in Python, so will not be microsecond-accurate.  The other thread is
        responsible for moving the stage, and records its current Z position 
        before and after each move.  Interpolating between these `(t, z)` points
        gives us a `z` value for each JPEG size, and so we can estimate the 
        JPEG size as a function of `z` and hence determine the `z` value at 
        which sharpness is maximised.
        """
        if not microscope:
            microscope = find_microscope_with_real_stage()
        with microscope.lock(timeout=1), microscope.camera.lock, microscope.stage.lock:
            with monitor_sharpness(microscope) as m:
                # Move to (-dz / 2)
                m.focus_rel(-dz / 2)
                # Move to dz while monitoring sharpness
                # i: Sharpness monitor index for this move
                # z: Final z position after move
                i, z = m.focus_rel(dz)
                # Get the z position with highest sharpness from the previous move (index i)
                fz: int = m.sharpest_z_on_move(i)
                # Move all the way to the start so it's consistent
                # Store final absolute z position from this return move
                i, z = m.focus_rel(-dz)
                # Move to the target position fz
                # Can't do absolute move here yet so move by (fz - z)
                m.focus_rel(fz - z)
                # Return all focus data
                return m.data_dict()

    @extension_action(
        args={
            "dz": fields.Int(
                load_default=500,
                metadata={
                    "description": "Total Z range to move down, then up (in stage steps)",
                    "example": 500,
                },
            ),
            "delay": fields.Int(
                load_default=5,
                metadata={
                    "description": "How long to measure sharpness for after the move, in seconds",
                    "example": 5,
                },
            ),
        }
    )
    def measure_settling_time(
        self, microscope: Optional[Microscope] = None, delay: int = 2, dz: int = 400
    ) -> Dict[str, np.ndarray]:
        """Make a Z move down then up by dz, then pause for delay while monitoring sharpness.
        This is useful so we can see how long we need to wait for the sharpness value to converge"""
        if not microscope:
            microscope = find_microscope_with_real_stage()
        with microscope.lock(timeout=1), microscope.camera.lock, microscope.stage.lock:
            with monitor_sharpness(microscope) as m:
                m.focus_rel(-dz)
                m.focus_rel(dz)
                m.hold(delay)
                return m.data_dict()

    @extension_action(
        args={
            "dz": fields.Int(
                load_default=2000,
                metadata={
                    "description": "Total Z range to search over (in stage steps)",
                    "example": 2000,
                },
            ),
            "target_z": fields.Int(
                load_default=0,
                metadata={
                    "description": "Target finishing position, relative to the focus.",
                    "example": -100,
                },
            ),
            "initial_move_up": fields.Bool(
                load_default=True,
                metadata={
                    "description": "Set to False to disable the initial move upwards"
                },
            ),
            "backlash": fields.Int(
                load_default=25,
                metadata={
                    "description": "Distance to undershoot, before correction move.",
                    "minimum": 0,
                },
            ),
        }
    )
    def fast_up_down_up_autofocus(
        self,
        microscope: Optional[Microscope] = None,
        dz: int = 2000,
        target_z: int = 0,
        initial_move_up: bool = True,
        backlash: Optional[int] = None,
        mini_backlash: Optional[int] = None,
    ) -> Dict[str, np.ndarray]:
        """Perform a fast up-down-up autofocus, with feedback
        
        Autofocus by measuring on the way down, and moving back up with feedback.
        This is a "fast" autofocus method, i.e. it moves the stage continuously
        while monitoring the sharpness using the MJPEG stream. See `fast_autofocus`
        for more details.

        This autofocus method is very efficient, as it only passes the peak once.
        The sequence of moves it performs is:

        1.  Move to the top of the range `dz/2` (can be disabled)

        2.  Move down by `dz` while monitoring JPEG size to find the focus.

        3.  Move back up to the `target_z` position, relative to the sharpest image.

        4.  Measure the sharpness, and compare against the curve recorded in (2) to \\
            estimate how much further we need to go.  Make this move, to reach our \\
            target position.

        Moving back to the target position in two steps allows us to correct for
        backlash, by using the sharpness-vs-z curve as a rough encoder for Z. The
        main source of error is that the curves on the way up and the way down are 
        not always identical, largely due to small lateral shifts as the Z axis is
        moved.

        Parameters:
          * `dz`: number of steps over which to scan (optional, default 2000)

          * `target_z`: we aim to finish at this position, relative to focus.  This may 
            be useful if, for example, you want to acquire a stack of images in Z. 
            It is optional, and the default value of 0 will finish at the focus.

          * `initial_move_up`: (optional, default True) set this to `False` to move down
            from the starting position.  Mostly useful if you're able to combine
            the initial move with something else, e.g. moving to the next scan point.

          * **backlash**: (optional, default 25) is a small extra move made in step
            3 to help counteract backlash.  It should be small enough that you
            would always expect there to be greater backlash than this.  Too small
            might slightly hurt accuracy, but is unlikely to be a big issue.  Too big
            may cause you to overshoot, which is a problem.

          * **mini_backlash**: (optional, default 25) is an alias for `backlash` and will be
            removed in due course.
        """
        if not microscope:
            microscope = find_microscope_with_real_stage()
        if not mini_backlash:  # I renamed the argument,
            mini_backlash = backlash or 25
        with microscope.lock(timeout=1), microscope.camera.lock, microscope.stage.lock:
            with monitor_sharpness(microscope) as m:
                # Ensure the MJPEG stream has started
                microscope.camera.start_stream()

                logging.debug("Initial move")
                if initial_move_up:
                    m.focus_rel(dz / 2)
                # move down
                logging.debug("Move down")
                i: int
                z: int
                i, z = m.focus_rel(-dz)
                # now inspect where the sharpest point is, and estimate the sharpness
                # (JPEG size) that we should find at the start of the Z stack
                jz: np.ndarray  # np.ndarray[float]
                js: np.ndarray  # np.ndarray[float]
                _, jz, js = m.move_data(i)
                best_z: int = jz[np.argmax(js)]

                # now move to the start of the z stack
                logging.debug("Move to the start of the z stack")
                i, z = m.focus_rel(
                    best_z + target_z - z + mini_backlash
                )  # takes us to the start of the stack

                # We've deliberately undershot - figure out how much further we should move based on the curve
                logging.debug("Calculate remining movement")
                current_js = m.camera.stream.last.size
                imax: int = int(
                    np.argmax(js)
                )  # we want to crop out just the bit below the peak
                js = js[imax:]  # NB z is in DECREASING order
                jz = jz[imax:]
                inow: int = int(
                    np.argmax(js < current_js)
                )  # use the curve we recorded to estimate our position

                # So, the Z position corresponding to our current sharpness value is zs[inow]
                # That means we should move forwards, by best_z - zs[inow]
                logging.debug("Correction move")
                correction_move: int = best_z + target_z - jz[inow]
                logging.debug(
                    "Fast autofocus scan: correcting backlash by moving %s steps",
                    (correction_move),
                )
                m.focus_rel(correction_move)
                return m.data_dict()


class MeasureSharpnessAPI(View):
    __doc__ = AutofocusExtension.measure_sharpness.__doc__

    def post(self):
        return {"sharpness": self.extension.measure_sharpness()}
