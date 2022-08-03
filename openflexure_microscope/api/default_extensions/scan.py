import datetime
import logging
import time
import uuid
from typing import Callable, Dict, List, Optional, Tuple

from flask import abort
import marshmallow
import numpy as np
from labthings import (
    current_action,
    fields,
    find_component,
    find_extension,
    update_action_progress,
)
from labthings.extensions import BaseExtension
from labthings.views import ActionView
from typing_extensions import Literal

from openflexure_microscope.api.v2.views.actions.camera import FullCaptureArgs
from openflexure_microscope.captures.capture_manager import generate_basename
from openflexure_microscope.microscope import Microscope

# Type alias for convenience
XyCoordinate = Tuple[int, int]
XyzCoordinate = Tuple[int, int, int]


### Grid construction


class FocusManager:
    """Manage axial motion during a series of XY moves

    This class keeps track of the focus position as we move around.
    It currently uses the regular autofocus method, and has support
    for background detection.
    """

    initial_position: XyzCoordinate = None  # type: ignore[assignment]
    focused_positions: List[XyzCoordinate] = None  # type: ignore[assignment]
    microscope: Microscope = None  # type: ignore[assignment]
    current_image_is_background_function: Optional[Callable] = None
    autofocus_function: Optional[Callable] = None
    axial_jump_threshold: Optional[float] = None

    def __init__(
        self,
        microscope: Microscope,
        initial_position: XyzCoordinate,
        autofocus_function: Optional[Callable],
        current_image_is_background_function: Optional[Callable] = None,
        axial_jump_threshold: Optional[float] = 0.4,
    ):
        """Set up management of axial motion.

        The `FocusManager` keeps track of previous positions where the
        microscope was in focus, and will estimate the best Z value for
        future XY positions.

        Arguments:
        * microscope: The microscope object.
        * initial_position: the XYZ position of the start of the scan
        * autofocus: A function that performs an autofocus.
        * current_image_is_background: a function that returns `True`
        if the microscope is currently looking at an empty field.
        * axial_jump_threshold: the maximum ratio between axial and
        lateral moves.  If this is not None, it will not count the 
        autofocus routine as successful if the focus moves more than
        this ratio times the lateral move between two points.  This can
        help avoid focus drift due to accidentally focusing on the coverslip.

        If either of the `autofocus` or `current_image_is_background`
        functions are None, we will neither perform an autofocus, nor 
        use background estimation.
        """
        self.initial_position = initial_position
        self.focused_positions = []
        self.microscope = microscope
        self.autofocus_function = autofocus_function
        if not autofocus_function:
            logging.info("Setting up FocusManager with autofocus disabled.")
        self.current_image_is_background_function = current_image_is_background_function
        self.axial_jump_threshold = axial_jump_threshold

    def record_focused_point(self, position: XyzCoordinate):
        """Add a position to the list of successfully-focused points"""
        self.focused_positions.append(position)

    def closest_focused_point(self, position: XyCoordinate) -> Optional[XyzCoordinate]:
        """The closest point in our list of focused points to a given XY position."""
        return closest_point_in_xy(position, self.focused_positions)

    def estimate_z(self, position: XyCoordinate) -> int:
        """Estimate the z position most likely to be in focus at an XY point
        
        The next z position is estimated based on the closest point that was in focus.
        For a snake/spiral scan, this should always be the last point, unless
        it's skipped for some reason.  In a raster scan, this should be the last
        point, except when we're at the start of a row when it will be the first
        point of the preceding row.
        
        It is possible that for some scan geometries, we won't be using the most
        recent point (e.g. if X and Y spacing in a raster scan are very different).
        This does not happen with the default settings used for raster scanning
        clinical samples.
        """
        closest_focused_point = self.closest_focused_point(position)
        if closest_focused_point:
            return closest_focused_point[2]
        else:
            return self.initial_position[2]

    def check_for_axial_jumps(self, position: XyzCoordinate) -> bool:
        """Check if a position is inconsistent with previous positions.

        This function returns `True` if the specified position is not consistent
        with the list of previously-visited positions, i.e. it's made a big axial
        move but a small lateral move.

        The threshold is set by `self.axial_jump_threshold`, and if that is `None`
        no check is performed.  Sensible values are probably between 0.1 and 0.5.
        """
        if not self.axial_jump_threshold:
            return False
        closest_focused_point = self.closest_focused_point(position[:2])
        if not closest_focused_point:
            return False
        move = np.array(position) - np.array(closest_focused_point)
        lateral_move = np.sqrt(np.sum(move[:2] ** 2))
        axial_move = np.abs(move[2])
        return axial_move > lateral_move * self.axial_jump_threshold

    def autofocus(self):
        """Perform an autofocus routine.

        If autofocus is disabled, nothing happens here.  If it is enabled, we optionally
        check whether there's anything in the image to focus on, and then run the autofocus
        routine.
        """
        if not self.autofocus_function:
            logging.debug("Autofocus is disabled, skipping autofocus.")
            return
        if self.current_image_is_background_function:
            # If it's been set, call the background detect function and skip
            # autofocus if appropriate
            if self.current_image_is_background_function():
                here = self.microscope.stage.position
                logging.info(f"Detected an empty field at {here}, skipping autofocus.")
                return
        # Assuming it's not disabled, and we're not skipping it, actually run the autofocus now
        self.autofocus_function()
        # Now, check for big jumps and record the new position if we've not made a big jump
        here = self.microscope.stage.position
        if self.check_for_axial_jumps(here):
            logging.warning(
                f"During a scan, there was a large axial jump from "
                f"{self.closest_focused_point(here[:2])}"
                f" to {here}.  This may mean autofocus has failed."
            )
        else:
            # If there has not been a jump in focus, record the point as successful
            self.record_focused_point(here)


def construct_grid(
    initial: XyCoordinate,
    step_sizes: XyCoordinate,
    n_steps: XyCoordinate,
    style: Literal["raster", "snake", "spiral"] = "raster",
) -> List[List[XyCoordinate]]:
    """
    Given an initial position, step sizes, and number of steps,
    construct a 2-dimensional list of scan x-y positions.
    """
    arr: List[List[XyCoordinate]] = []  # 2D array of coordinates

    if style == "spiral":
        # deal with the centre image immediately
        coord = initial
        arr.append([initial])
        # for spiral, n_steps is the number of shells, and so only requires n_steps[0]
        for i in range(2, n_steps[0] + 1):
            arr.append([])  # Append new shell holder
            side_length = (2 * i) - 1

            # Iteratively generate the next location to append

            # Start coordinate of the shell
            # We create a copy of coord so that the new value of coord doesn't depend on itself
            # Otherwise we create a generator, not a tuple, which makes type checking angry
            last_coordinate: XyCoordinate = coord
            coord = (
                last_coordinate[0] + [-1, 1][0] * step_sizes[0],
                last_coordinate[1] + [-1, 1][1] * step_sizes[1],
            )
            for direction in ([1, 0], [0, -1], [-1, 0], [0, 1]):
                for _ in range(side_length - 1):
                    last_coordinate = coord
                    coord = (
                        last_coordinate[0] + direction[0] * step_sizes[0],
                        last_coordinate[1] + direction[1] * step_sizes[1],
                    )
                    arr[i - 1].append(coord)

    # If raster or snake
    else:
        for i in range(n_steps[0]):  # x axis
            arr.append([])
            for j in range(n_steps[1]):  # y axis
                # Create a coordinate tuple
                coord = (
                    initial[0] + [i, j][0] * step_sizes[0],
                    initial[1] + [i, j][1] * step_sizes[1],
                )
                # Append coordinate array to position grid
                arr[i].append(coord)

        # Style modifiers
        if style == "snake":
            # For each line (row) in the coordinate array
            for i, line in enumerate(arr):
                # If it's an odd row
                if i % 2 != 0:
                    # Reverse the list of coordinates
                    line.reverse()

    return arr


def construct_grid_1d(
    initial: XyCoordinate,
    step_sizes: XyCoordinate,
    n_steps: XyCoordinate,
    style: Literal["raster", "snake", "spiral"] = "raster",
) -> List[XyCoordinate]:
    """Construct coordinates for a scan, returning a 1D list.

    This is the same set of coordinates returned by `construct_grid`
    but the list-of-lists is flattened to a simple list.
    """
    path = []
    grid = construct_grid(
        initial=initial, step_sizes=step_sizes, n_steps=n_steps, style=style
    )
    for line in grid:
        path += line  # concatenate the lists
    return path


def closest_point_in_xy(
    current_position: XyCoordinate, points: List[XyzCoordinate]
) -> Optional[XyzCoordinate]:
    """Find the closest point in a list

    Given a 2D position, find the 3D position that's closest in XY and return it.
    In the event of a tie, the most recent (i.e. latest in the list) is returned.

    If the list is empty, we return None
    """
    if len(points) < 1:
        return None
    points_2d = np.asarray(points)[:, :2]

    squared_distances = np.sum((points_2d - current_position) ** 2, axis=1)
    # We reverse the distances before searching, as argmin will return the first
    # point in the event of there being multiple points with the same minimum,
    # and we want to pick the last one.
    reverse_min_index = np.argmin(squared_distances[::-1])
    # of course, now we must convert the index to be the right way round
    min_index = len(points) - 1 - reverse_min_index
    return points[int(min_index)]  # The explicit cast is necessary for MyPy


### Capturing


class ScanExtension(BaseExtension):
    def __init__(self):
        BaseExtension.__init__(self, "org.openflexure.scan", version="2.0.0")

        self._images_to_be_captured: int = 1
        self._images_captured_so_far: int = 0

        self.add_view(TileScanAPI, "/tile", endpoint="tile")

    def capture(
        self,
        microscope: Microscope,
        basename: Optional[str],
        namemode: str = "coordinates",
        temporary: bool = False,
        use_video_port: bool = False,
        resize: Optional[Tuple[int, int]] = None,
        bayer: bool = False,
        metadata: Optional[dict] = None,
        annotations: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        dataset: Optional[Dict[str, str]] = None,
    ):
        metadata = metadata or {}
        annotations = annotations or {}
        tags = tags or []

        # Construct a tile filename
        if namemode == "coordinates":
            filename = "{}_{}_{}_{}".format(basename, *microscope.stage.position)
        else:
            filename = "{}_{}".format(
                basename,
                str(self._images_captured_so_far).zfill(
                    len(str(self._images_to_be_captured))
                ),
            )
        folder = "SCAN_{}".format(basename)

        # Do capture
        return microscope.capture(
            filename=filename,
            folder=folder,
            temporary=temporary,
            use_video_port=use_video_port,
            resize=resize,
            bayer=bayer,
            annotations=annotations,
            tags=tags,
            dataset=dataset,
            metadata=metadata,
            cache_key=folder,
        )

    def progress(self):
        progress = (self._images_captured_so_far / self._images_to_be_captured) * 100
        logging.info(progress)
        return progress

    def get_autofocus_function(self, dz: int, use_fast_autofocus: bool) -> Callable:
        """Return a function that will perform an autofocus routine.

        This should be called at the start of a scan.  It will check that
        the necessary hardware and software are present, and raise a helpful
        error if they are not.
        """
        microscope = find_component("org.openflexure.microscope")
        # Locate the autofocus extension
        autofocus_extension = find_extension("org.openflexure.autofocus")
        if not autofocus_extension:
            raise RuntimeError(
                "The Autofocus extension is missing: select 'None' as your autofocus "
                "type to scan without autofocusing."
            )
        if not (microscope.has_real_stage() and microscope.has_real_camera()):
            raise RuntimeError(
                "A real stage and camera are needed in order to autofocus.  You can "
                "still run a scan without autofocus."
            )

        if use_fast_autofocus:

            def autofocus():
                # Run fast autofocus. Client should provide dz ~ 2000
                autofocus_extension.fast_autofocus(microscope, dz=dz)
                time.sleep(0.5)

            return autofocus
        else:

            def autofocus():
                # Run slow autofocus. Client should provide dz ~ 50
                autofocus_extension.autofocus(microscope, range(-3 * dz, 4 * dz, dz))
                time.sleep(0.5)

            return autofocus

    def get_background_detect_function(self):
        """Return a function that returns true if we are looking at background"""
        # Check for the background detect extension, raise an error now if it's missing.
        background_detect_extension = find_extension(
            "org.openflexure.background-detect"
        )
        if not background_detect_extension:
            raise RuntimeError(
                "Detecting background fields requires the background detect extension and it was not found."
            )

        def current_image_is_background():
            verdict = background_detect_extension.grab_and_classify_image()
            logging.debug(f"Background detection verdict: {verdict}")
            return verdict["classification"] == "background"

        return current_image_is_background

    ### Scanning
    def tile(
        self,
        microscope: Microscope,
        basename: Optional[str] = None,
        namemode: str = "coordinates",
        temporary: bool = False,
        stride_size: XyzCoordinate = (2000, 1500, 100),
        grid: XyzCoordinate = (3, 3, 5),
        style="raster",
        autofocus_dz: int = 50,
        use_video_port: bool = False,
        resize: Optional[Tuple[int, int]] = None,
        bayer: bool = False,
        fast_autofocus: bool = False,
        metadata: Optional[dict] = None,
        annotations: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        detect_empty_fields_and_skip_autofocus: bool = False,
    ):
        metadata = metadata or {}
        annotations = annotations or {}
        tags = tags or []

        start = time.time()

        # Store initial position
        initial_position = microscope.stage.position
        # Construct an x-y scan path (list of 2D coordinates)
        path = construct_grid_1d(
            initial_position[:2], stride_size[:2], grid[:2], style=style
        )

        # Keep task progress
        self._images_to_be_captured = len(path)
        self._images_captured_so_far = 0

        # Generate a basename if none given
        if not basename:
            basename = generate_basename()

        # Add dataset metadata
        dataset_d = {
            "id": uuid.uuid4(),
            "type": "xyzScan",
            "name": basename,
            "acquisitionDate": datetime.datetime.now().isoformat(),
            "strideSize": stride_size,
            "grid": grid,
            "style": style,
            "autofocusDz": autofocus_dz,
        }

        # Perform set-up to be able to autofocus, if needed
        autofocus: Optional[Callable] = None
        if autofocus_dz:
            autofocus = self.get_autofocus_function(
                dz=autofocus_dz, use_fast_autofocus=fast_autofocus
            )
        if detect_empty_fields_and_skip_autofocus:
            current_image_is_background = self.get_background_detect_function()
        else:
            current_image_is_background = None
        focus_manager = FocusManager(
            microscope,
            initial_position,
            autofocus_function=autofocus,
            current_image_is_background_function=current_image_is_background,
            axial_jump_threshold=0.4
            if detect_empty_fields_and_skip_autofocus
            else None,
        )

        # Now step through each point in the x-y coordinate array
        for x_y in path:
            next_z = focus_manager.estimate_z(x_y)
            # Move to new grid position
            logging.debug("Moving to step %s", ([x_y[0], x_y[1], next_z]))
            microscope.stage.move_abs((x_y[0], x_y[1], next_z))
            # Autofocus (if requested)
            focus_manager.autofocus()

            # If we're not doing a z-stack, just capture
            if grid[2] <= 1:
                self.capture(
                    microscope,
                    basename,
                    namemode=namemode,
                    temporary=temporary,
                    use_video_port=use_video_port,
                    resize=resize,
                    bayer=bayer,
                    dataset=dataset_d,
                    annotations=annotations,
                    tags=tags,
                )
                # Update task progress
                self._images_captured_so_far += 1
                update_action_progress(self.progress())
            else:
                logging.debug("Entering z-stack")
                self.stack(
                    microscope=microscope,
                    basename=basename,
                    namemode=namemode,
                    temporary=temporary,
                    step_size=stride_size[2],
                    steps=grid[2],
                    use_video_port=use_video_port,
                    resize=resize,
                    bayer=bayer,
                    dataset=dataset_d,
                    annotations=annotations,
                    tags=tags,
                )
            # Gracefully shut down if we have been requested to stop
            if current_action() and current_action().stopped:
                return

        logging.debug("Returning to %s", (initial_position))
        microscope.stage.move_abs(initial_position)

        end = time.time()
        logging.info("Scan took %s seconds", end - start)

    def stack(
        self,
        microscope: Microscope,
        basename: Optional[str] = None,
        namemode: str = "coordinates",
        temporary: bool = False,
        step_size: int = 100,
        steps: int = 5,
        return_to_start: bool = True,
        use_video_port: bool = False,
        resize: Optional[Tuple[int, int]] = None,
        bayer: bool = False,
        metadata: Optional[dict] = None,
        annotations: Optional[Dict[str, str]] = None,
        dataset: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
    ):
        metadata = metadata or {}
        annotations = annotations or {}
        tags = tags or []

        # Store initial position
        initial_position = microscope.stage.position
        logging.debug("Starting z-stack from position %s", microscope.stage.position)

        with microscope.lock:
            # Move to center scan
            logging.debug("Moving to z-stack starting position")
            microscope.stage.move_rel((0, 0, int((-step_size * steps) / 2)))
            logging.debug("Starting scan from position %s", microscope.stage.position)

            for i in range(steps):
                time.sleep(0.1)
                logging.debug("Capturing from position %s", microscope.stage.position)
                self.capture(
                    microscope,
                    basename,
                    namemode=namemode,
                    temporary=temporary,
                    use_video_port=use_video_port,
                    resize=resize,
                    bayer=bayer,
                    metadata=metadata,
                    annotations=annotations,
                    dataset=dataset,
                    tags=tags,
                )
                # Update task progress
                self._images_captured_so_far += 1
                update_action_progress(self.progress())
                if current_action() and current_action().stopped:
                    return

                if i != steps - 1:
                    logging.debug("Moving z by %s", (step_size))
                    microscope.stage.move_rel((0, 0, step_size))
            if return_to_start:
                logging.debug("Returning to %s", (initial_position))
                microscope.stage.move_abs(initial_position)


class TileScanArgs(FullCaptureArgs):
    namemode = fields.String(missing="coordinates", example="coordinates")
    grid = fields.List(
        fields.Integer(validate=marshmallow.validate.Range(min=1)),
        missing=[3, 3, 3],
        example=[3, 3, 3],
    )
    style = fields.String(missing="raster")
    autofocus_dz = fields.Integer(missing=50)
    fast_autofocus = fields.Boolean(missing=False)
    stride_size = fields.List(
        fields.Integer, missing=[2000, 1500, 100], example=[2000, 1500, 100]
    )
    detect_empty_fields_and_skip_autofocus = fields.Boolean(missing=False)


class TileScanAPI(ActionView):
    args = TileScanArgs()

    # Allow 10 seconds to stop upon DELETE request
    # Gives fast-autofocus time to finish if it's running
    default_stop_timeout = 10

    def post(self, args):
        microscope = find_component("org.openflexure.microscope")

        if not microscope:
            abort(503, "No microscope connected. Unable to autofocus.")

        resize = args.get("resize", None)
        if resize:
            if ("width" in resize) and ("height" in resize):
                resize = (
                    int(resize["width"]),
                    int(resize["height"]),
                )  # Convert dict to tuple
            else:
                abort(404)

        logging.info("Running tile scan...")

        # Acquire microscope lock with 1s timeout
        with microscope.lock(timeout=1):
            # Run scan_extension_v2
            return self.extension.tile(
                microscope,
                basename=args.get("filename"),
                namemode=args.get("namemode"),
                temporary=args.get("temporary"),
                stride_size=args.get("stride_size"),
                grid=args.get("grid"),
                style=args.get("style"),
                autofocus_dz=args.get("autofocus_dz"),
                use_video_port=args.get("use_video_port"),
                resize=resize,
                bayer=args.get("bayer"),
                fast_autofocus=args.get("fast_autofocus"),
                annotations=args.get("annotations"),
                tags=args.get("tags"),
                detect_empty_fields_and_skip_autofocus=args.get(
                    "detect_empty_fields_and_skip_autofocus"
                ),
            )
