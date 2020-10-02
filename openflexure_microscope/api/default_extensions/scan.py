import itertools
import logging
import uuid
import datetime
from typing import Tuple
from functools import reduce

from openflexure_microscope.captures.capture_manager import generate_basename

from labthings import fields, find_component, find_extension, current_action, update_action_progress
from labthings.views import View, ActionView
from labthings.extensions import BaseExtension

from openflexure_microscope.devel import abort

import time


### Grid construction


def construct_grid(initial, step_sizes, n_steps, style="raster"):
    """
    Given an initial position, step sizes, and number of steps,
    construct a 2-dimensional list of scan x-y positions.
    """
    arr = []

    for i in range(n_steps[0]):  # x axis
        arr.append([])
        for j in range(n_steps[1]):  # y axis
            # Create a coordinate array
            coord = [initial[ax] + [i, j][ax] * step_sizes[ax] for ax in range(2)]
            # Append coordinate array to position grid
            arr[i].append(tuple(coord))

    # Style modifiers
    if style == "snake":
        for i, line in enumerate(arr):
            if i % 2 != 0:
                line.reverse()

    return arr


def flatten_grid(grid):
    """
    Convert a 3D list of scan positions into a flat list
    of sequential positions. 
    """

    grid = list(itertools.chain(*grid))
    return grid


### Capturing





class ScanExtension(BaseExtension):
    def __init__(self):
        self._images_to_be_captured: int = 1
        self._images_captured_so_far: int = 0
        BaseExtension.__init__(self, "org.openflexure.scan", version="2.0.0")

    def capture(
        self,
        microscope,
        basename,
        namemode: str = "coordinates",
        temporary: bool = False,
        use_video_port: bool = False,
        resize: Tuple[int, int] = None,
        bayer: bool = False,
        metadata: dict = {},
        annotations: dict = {},
        tags: list = [],
    ):

        # Construct a tile filename
        if namemode == "coordinates":
            filename = "{}_{}_{}_{}".format(basename, *microscope.stage.position)
        else:
            filename = "{}_{}".format(basename, str(self._images_captured_so_far).zfill(len(str(self._images_to_be_captured))))
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
            metadata=metadata,
            cache_key=folder
        )

    def progress(self):
        progress = (self._images_captured_so_far / self._images_to_be_captured) * 100
        logging.info(progress)
        return progress
        
    ### Scanning
    def tile(
        self,
        microscope,
        basename: str = None,
        namemode: str = "coordinates",
        temporary: bool = False,
        stride_size: int = [2000, 1500, 100],
        grid: list = [3, 3, 5],
        style="raster",
        autofocus_dz: int = 50,
        use_video_port: bool = False,
        resize: Tuple[int, int] = None,
        bayer: bool = False,
        fast_autofocus=False,
        metadata: dict = {},
        annotations: dict = {},
        tags: list = [],
    ):
        start = time.time()

        # Keep task progress
        self._images_to_be_captured = reduce((lambda x, y: x * y), grid)
        self._images_captured_so_far = 0

        # Generate a basename if none given
        if not basename:
            basename = generate_basename()

        # Store initial position
        initial_position = microscope.stage.position

        # Add dataset metadata
        dataset_d = {
            "dataset": {
                "id": uuid.uuid4(),
                "type": "xyzScan",
                "name": basename,
                "acquisitionDate": datetime.datetime.now().isoformat(),
                "strideSize": stride_size,
                "grid": grid,
                "style": style,
                "autofocusDz": autofocus_dz,
            }
        }

        # Check if autofocus is enabled
        autofocus_extension = find_extension("org.openflexure.autofocus")
        if (
            autofocus_dz
            and autofocus_extension
            and microscope.has_real_stage()
            and microscope.has_real_camera()
        ):
            autofocus_enabled = True
        else:
            autofocus_enabled = False

        # Construct an x-y grid (worry about z later)
        x_y_grid = construct_grid(initial_position, stride_size[:2], grid[:2], style=style)

        # Keep the initial Z position the same as our current position
        initial_z = initial_position[2]
        next_z = initial_z  # Save this value for use in raster scans

        # Now step through each point in the x-y coordinate array
        for line in x_y_grid:
            # If rastering, rather than snake (or eventually spiral)
            # Return focus to initial position
            if style == "raster":
                next_z = initial_z  # Reset z position at start of each new row
                logging.debug("Returning to initial z position")
                microscope.stage.move_abs(
                    [line[0][0], line[0][1], next_z]
                )  # RWB: I think this line is redundant

            for x_y in line:
                # Move to new grid position without changing z
                logging.debug("Moving to step {}".format([x_y[0], x_y[1], next_z]))
                microscope.stage.move_abs([x_y[0], x_y[1], next_z])
                # Refocus
                if autofocus_enabled:
                    if fast_autofocus:
                        # Run fast autofocus. Client should provide dz ~ 2000
                        autofocus_extension.fast_up_down_up_autofocus(
                            microscope, dz=autofocus_dz
                        )
                    else:
                        # Run slow autofocus. Client should provide dz ~ 50
                        autofocus_extension.autofocus(
                            microscope,
                            range(-3 * autofocus_dz, 4 * autofocus_dz, autofocus_dz),
                        )
                        logging.debug("Finished autofocus")
                        time.sleep(1)

                # If we're not doing a z-stack, just capture
                if grid[2] <= 1:
                    capture(
                        microscope,
                        basename,
                        namemode=namemode,
                        temporary=temporary,
                        use_video_port=use_video_port,
                        resize=resize,
                        bayer=bayer,
                        metadata=dataset_d,
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
                        metadata=dataset_d,
                        annotations=annotations,
                        tags=tags,
                    )
                if current_action() and current_action().stopped:
                    return
                # Make sure we use our current best estimate of focus (i.e. the current position) next point
                next_z = microscope.stage.position[2]

        logging.debug("Returning to {}".format(initial_position))
        microscope.stage.move_abs(initial_position)

        end = time.time()
        logging.info(f"Scan took {end - start} seconds")


    def stack(
        self,
        microscope,
        basename: str = None,
        namemode: str = "coordinates",
        temporary: bool = False,
        step_size: int = 100,
        steps: int = 5,
        return_to_start: bool = True,
        use_video_port: bool = False,
        resize: Tuple[int, int] = None,
        bayer: bool = False,
        metadata: dict = {},
        annotations: dict = {},
        tags: list = [],
    ):

        # Store initial position
        initial_position = microscope.stage.position
        logging.debug(f"Starting z-stack from position {microscope.stage.position}")

        with microscope.lock:
            # Move to center scan
            logging.debug("Moving to z-stack starting position")
            microscope.stage.move_rel([0, 0, int((-step_size * steps) / 2)])
            logging.debug(f"Starting scan from position {microscope.stage.position}")

            for i in range(steps):
                time.sleep(0.1)
                logging.debug(f"Capturing from position {microscope.stage.position}")
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
                    tags=tags,
                )
                # Update task progress
                self._images_captured_so_far += 1
                update_action_progress(self.progress())
                if current_action() and current_action().stopped:
                    return

                if i != steps - 1:
                    logging.debug("Moving z by {}".format(step_size))
                    microscope.stage.move_rel([0, 0, step_size])
            if return_to_start:
                logging.debug("Returning to {}".format(initial_position))
                microscope.stage.move_abs(initial_position)


scan_extension_v2 = ScanExtension()

class TileScanAPI(ActionView):
    args = {
        "filename": fields.String(missing=None, example=None),
        "namemode": fields.String(missing="coordinates", example="coordinates"),
        "temporary": fields.Boolean(missing=False),
        "stride_size": fields.List(
            fields.Integer, missing=[2000, 1500, 100], example=[2000, 1500, 100]
        ),
        "grid": fields.List(fields.Integer, missing=[3, 3, 3], example=[3, 3, 3]),
        "style": fields.String(missing="raster"),
        "autofocus_dz": fields.Integer(missing=50),
        "fast_autofocus": fields.Boolean(missing=False),
        "use_video_port": fields.Boolean(missing=False),
        "bayer": fields.Boolean(missing=False),
        "annotations": fields.Dict(missing={}, example={"Foo": "Bar"}),
        "tags": fields.List(fields.String, missing=[]),
        "resize": fields.Dict(missing=None),  # TODO: Validate keys
    }

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
            return scan_extension_v2.tile(
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
            )

scan_extension_v2.add_view(TileScanAPI, "/tile", endpoint="tile")
