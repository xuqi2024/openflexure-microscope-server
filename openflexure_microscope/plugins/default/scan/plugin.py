import time
import numpy as np
from typing import Tuple
import uuid
import itertools
import logging

from openflexure_microscope.camera.base import generate_basename

from openflexure_microscope.devel import MicroscopePlugin

from .api import TileScanAPI

def construct_grid(initial, step_sizes, n_steps, style='raster'):
    """
    Given an initial position, step sizes, and number of steps,
    construct a 2-dimensional list of scan x-y positions.
    """
    arr = []

    for i in range(n_steps[0]): # x axis
        arr.append([])
        for j in range(n_steps[1]): # y axis
            # Create a coordinate array
            coord = [initial[ax] + [i, j][ax]*step_sizes[ax] for ax in range(2)]
            # Append coordinate array to position grid
            arr[i].append(tuple(coord))

    # Style modifiers
    if style == 'snake':
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

class ScanPlugin(MicroscopePlugin):
    """
    Stack and tile plugin
    """

    api_views = {
        '/tile': TileScanAPI,
    }

    def capture(self,
                basename,
                scan_id,
                temporary: bool = False,
                use_video_port: bool = False,
                resize: Tuple[int, int] = None,
                bayer: bool = False,
                metadata: dict = {},
                tags: list = []):

        # Construct a tile filename
        filename = "{}_{}_{}_{}".format(basename, *self.microscope.stage.position)
        folder = "SCAN_{}".format(basename)

        # Create output object
        output = self.microscope.camera.new_image(
            write_to_file=True,
            temporary=temporary,
            filename=filename,
            folder=folder)

        # Capture
        self.microscope.camera.capture(
            output,
            use_video_port=use_video_port,
            resize=resize,
            bayer=bayer)

        # Affix metadata
        if 'scan' not in tags:
            tags.append('scan')

        metadata.update({
            'position': self.microscope.state['stage']['position'],
            'scan_id': scan_id,
            'basename': basename,
            'microscope_id': self.microscope.id,
            'microscope_name': self.microscope.name
        })

        output.put_metadata(metadata)
        output.put_tags(tags)

    def tile(
            self,
            basename: str = None,
            temporary: bool = False,
            step_size: int = [2000, 1500, 100],
            grid: list = [3, 3, 5],
            style='raster',
            autofocus_dz: int = 50,
            use_video_port: bool = False,
            resize: Tuple[int, int] = None,
            bayer: bool = False,
            fast_autofocus = False,
            metadata: dict = {},
            tags: list = []):

        # Generate a basename if none given
        if not basename:
            basename = generate_basename()

        # Generate a stack ID
        scan_id = uuid.uuid4().hex

        # Store initial position
        initial_position = self.microscope.stage.position

        # Add scan metadata
        if not 'time' in metadata:
            metadata['time'] = generate_basename()

        # Check if autofocus is enabled
        if autofocus_dz and hasattr(self.microscope.plugin, 'default_autofocus'):
            autofocus_enabled = True
        else:
            autofocus_enabled = False

        if fast_autofocus and not hasattr(self.microscope.plugin.default_autofocus, 'monitor_sharpness'):
            logging.error("Can't use fast autofocus in the scan - the default plugin doesn't support monitor_sharpness; maybe it is too old?")
            fast_autofocus = False
        z_stack_dz = grid[2] * step_size[2] if grid[2] > 1 else 0 # shorthand for Z stack range

        # Construct an x-y grid (worry about z later)
        x_y_grid = construct_grid(
            initial_position, 
            step_size[:2], 
            grid[:2],
            style=style
        )

        # Keep the initial Z position the same as our current position
        next_z = initial_position[2]
        if fast_autofocus:           # If fast autofocus is enabled, make
            next_z += autofocus_dz/2 # sure we start from the top of the range
        initial_z = next_z # Save this value for use in raster scans

        # Now step through each point in the x-y coordinate array
        for line in x_y_grid:
            # If rastering, rather than snake (or eventually spiral)
            # Return focus to initial position
            if style == 'raster':
                next_z = initial_z
                logging.debug("Returning to initial z position")
                self.microscope.stage.move_abs([line[0][0], line[0][1], next_z]) #RWB: I think this line is redundant

            for x_y in line:
                # Move to new grid position without changing z
                logging.debug("Moving to step {}".format([x_y[0], x_y[1], next_z]))
                self.microscope.stage.move_abs([x_y[0], x_y[1], next_z])
                # Refocus
                if autofocus_enabled:
                    if fast_autofocus:
                        self.microscope.plugin.default_autofocus.fast_up_down_up_autofocus(
                                dz=autofocus_dz,
                                target_z=-z_stack_dz/2.0, # Finish below the focus
                                initial_move_up=False, # We're already at the top of the scan
                                )
                        #TODO: save the focus data for future reference? Use it for diagnostics?
                    else:
                        logging.debug("Running autofocus")
                        self.microscope.plugin.default_autofocus.autofocus(
                            range(-3 * autofocus_dz, 4 * autofocus_dz, autofocus_dz))
                        logging.debug("Finished autofocus")
                        time.sleep(1)  # TODO: Remove

                # If we're not doing a z-stack, just capture
                if (grid[2] <= 1):
                    self.capture(
                        basename,
                        scan_id,
                        temporary=temporary,
                        use_video_port=use_video_port,
                        resize=resize,
                        bayer=bayer,
                        metadata=metadata,
                        tags=tags
                    )
                else:
                    logging.debug("Entering z-stack")
                    self.stack(
                        basename=basename,
                        temporary=temporary,
                        scan_id=scan_id,
                        step_size=step_size[2],
                        steps=grid[2],
                        center=not fast_autofocus, # fast_autofocus does this for us!
                        return_to_start=not fast_autofocus,
                        use_video_port=use_video_port,
                        resize=resize,
                        bayer=bayer,
                        metadata=metadata,
                        tags=tags
                    )
                # Make sure we use our current best estimate of focus (i.e. the current position) next point
                next_z = self.microscope.stage.position[2]
                if fast_autofocus:
                    next_z += autofocus_dz/2 # Fast autofocus requires us to start at the top of the range
                    if grid[2] > 1:
                        next_z -= int(grid[2]/2.0*step_size[2]) # Z stacking means we're higher up to start with

        logging.debug("Returning to {}".format(initial_position))
        self.microscope.stage.move_abs(initial_position)

    def stack(
            self,
            basename: str = None,
            temporary: bool = False,
            scan_id: str = None,
            step_size: int = 100,
            steps: int = 5,
            center: bool = True,
            return_to_start: bool = True,
            use_video_port: bool = False,
            resize: Tuple[int, int] = None,
            bayer: bool = False,
            metadata: dict = {},
            tags: list = []):

        # Generate a basename if none given
        if not basename:
            basename = generate_basename()

        # Generate a stack ID
        if not scan_id:
            scan_id = uuid.uuid4().hex

        # Add scan metadata
        if not 'time' in metadata:
            metadata['time'] = generate_basename()

        # Store initial position
        initial_position = self.microscope.stage.position


        with self.microscope.lock:
            # Move to center scan
            if center:
                logging.debug("Moving to starting position")
                self.microscope.stage.move_rel([0, 0, int((-step_size * steps) / 2)])

            for i in range(steps):
                time.sleep(0.1)
                logging.debug("Capturing...")
                self.capture(
                    basename,
                    scan_id,
                    temporary=temporary,
                    use_video_port=use_video_port,
                    resize=resize,
                    bayer=bayer,
                    metadata=metadata,
                    tags=tags
                )

                if i != steps - 1:
                    logging.debug("Moving z by {}".format(step_size))
                    self.microscope.stage.move_rel([0, 0, step_size])
            if return_to_start:
                logging.debug("Returning to {}".format(initial_position))
                self.microscope.stage.move_abs(initial_position)
