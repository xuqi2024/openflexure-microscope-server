import os
import pickle

import numpy as np
from scipy import interpolate
from matplotlib import pyplot as plt
from matplotlib.path import Path as MatPath
from matplotlib.patches import PathPatch
from matplotlib.figure import Figure

from openflexure_microscope_server import scan_planners

THIS_DIR = os.path.dirname(os.path.realpath(__file__))


class FakeSample:
    """A fake sample to test scan algorithms.

    The sample is able to return whether a given position is sample, there is no image
    associated with the sample
    """

    def __init__(self, xy_points: list[tuple[int, int]]):
        """Create the sample from a spline interpolation around the given points."""
        self._sample_perimeter = interp_closed_path(xy_points, 500)

    def is_sample(self, pos: tuple[int, int], im_size: tuple[int, int]) -> bool:
        """Return True if an image at a given location is on the sample.

        The image size is specified to check if it overlaps the sample. It doesn't
        check the entire image field as this is designed to be used where the fake
        sample is much larger than the image and has smooth edges. It just checks the
        4 corners.
        """
        img_corners = [
            (pos[0] + im_size[0], pos[1] + im_size[1]),
            (pos[0] + im_size[0], pos[1] - im_size[1]),
            (pos[0] - im_size[0], pos[1] + im_size[1]),
            (pos[0] - im_size[0], pos[1] - im_size[1]),
        ]
        return any(
            self._sample_perimeter.contains_point(corner) for corner in img_corners
        )

    @property
    def patch(self) -> PathPatch:
        """The sample as a matplotlib patch for plotting."""
        patch = PathPatch(self._sample_perimeter)
        patch.set(color=(1.0, 0.8, 1.0, 1.0))
        return patch


def visualise_scan(sample: FakeSample, planner: scan_planners.ScanPlanner) -> Figure:
    """For a given sample and scanner object return a matplotlib figure of the scan."""
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.add_artist(sample.patch)
    xh, yh = zip(*planner._path_history)
    xi, yi, _ = zip(*planner._imaged_locations)

    # convert history to numpy array so can calculate quiver arrows
    xh = np.array(xh)
    yh = np.array(yh)

    plt.quiver(
        xh[:-1],
        yh[:-1],
        xh[1:] - xh[:-1],
        yh[1:] - yh[:-1],
        scale_units="xy",
        angles="xy",
        scale=1,
    )
    plt.plot(xh, yh, "r.")
    plt.plot(xi, yi, "g*")
    ax.axis("equal")
    return fig


def interp_closed_path(xy_points: list[tuple[int, int]], n_points: int) -> MatPath:
    """Interpolate an n_point closed curve from a lists of xy_points.

    This can be used to create an arbitrary sample shape for testing a scan planner.

    Modified from:
    https://stackoverflow.com/questions/33962717/interpolating-a-closed-curve-using-scipy
    """
    # Use zip to seperate x and y points into tuples
    x, y = zip(*xy_points)

    # Append first point and convert to array
    x = np.array(x + (x[0],))
    y = np.array(y + (y[0],))

    # fit splines to x=f(u) and y=g(u), treating both as periodic. also note that s=0
    # is needed in order to force the spline fit to pass through all the input points.
    spline_data, _ = interpolate.splprep([x, y], s=0, per=True)

    # evaluate the spline
    xi, yi = interpolate.splev(np.linspace(0, 1, n_points), spline_data)

    # Convert to a matplotlib closed path
    path_points = [[xp, yp] for xp, yp in (zip(xi, yi))]
    return MatPath(path_points, closed=True)


def example_smart_spiral(
    sample_name: str = "lobed",
) -> tuple[FakeSample, scan_planners.ScanPlanner]:
    """Run an example scan.

    :returns: The sample scanned and the planner object after scan is complete.
    """
    xy_sample_points = load_sample_points(sample_name)
    sample = FakeSample(xy_sample_points)
    img_size = (1000, 1000)
    intial_position = (0, 0)
    planner_settings = {"dx": 1200, "dy": 800, "max_dist": 100000}
    planner = scan_planners.SmartSpiral(
        intial_position=intial_position, planner_settings=planner_settings
    )

    while not planner.scan_complete:
        xy_pos, _ = planner.get_next_location_and_z_estimate()
        xyz_pos = (xy_pos[0], xy_pos[1], 0)
        imaged = sample.is_sample(xy_pos, img_size)
        planner.mark_location_visited(xyz_pos, imaged=imaged, focused=imaged)
    return sample, planner


def profile_and_save_plot_for_example_smart_spiral():
    """Run the example scan and save a plot and the profile data.

    Also print the cumulative stats.

    This runs if you run this file directly.
    """
    import pstats
    import cProfile

    profiler = cProfile.Profile()
    sample, planner = profiler.runcall(example_smart_spiral)

    stats_fname = os.path.join(THIS_DIR, "scan_example_stats.pstats")
    profiler.dump_stats(stats_fname)

    png_fname = os.path.join(THIS_DIR, "scan_example_plot.png")
    fig = visualise_scan(sample, planner)
    fig.savefig(png_fname, dpi=200)

    run_stats = pstats.Stats(stats_fname)
    run_stats.strip_dirs()
    run_stats.sort_stats("cumulative")
    run_stats.print_stats("scan_planners.py")


def update_example_smart_spiral_pickle(sample_name: str):
    """Pickle the ScanPlanner for the example_smart_spiral().

    This is done so the history can be compared by testing to check
    the algorithm is unchanged.

    If the algorithm is purposefully changed then this will need to be
    run to update the pickle for the test to pass.

    Takes sample, the sample type we have generated, so we can make a
    pickle for each sample type
    """
    pkl_fname = os.path.join(THIS_DIR, f"example_smart_spiral_{sample_name}.pkl")
    _, planner = example_smart_spiral(sample_name)
    with open(pkl_fname, "wb") as pkl_file_obj:
        pickle.dump(planner, pkl_file_obj, pickle.HIGHEST_PROTOCOL)


def get_expected_result_for_example_smart_spiral(
    sample_name: str,
) -> scan_planners.ScanPlanner:
    """Return the expected ScanPlanner object for the example_smart_spiral().

    This is loaded from a pickle so that the object can be committed to the repo.
    """
    pkl_fname = os.path.join(THIS_DIR, f"example_smart_spiral_{sample_name}.pkl")
    with open(pkl_fname, "rb") as pkl_file_obj:
        return pickle.load(pkl_file_obj)


def load_sample_points(sample_name: str):
    """Return the points to generate the FakeSample corresponding to the given input name.

    Options are "lobed", "regular", and "core".
    """
    sample_options = {
        "lobed": [
            (-5000, -5000),
            (-2000, 16000),
            (1000, 2000),
            (6000, 7000),
            (9000, 2000),
        ],
        "regular": [
            (-5000, -5000),
            (-5000, 5000),
            (5000, 5000),
            (5000, -5000),
        ],
        "core": [
            (-12000, 2000),
            (-12000, 1000),
            (0, -2000),
            (10000, -2000),
            (10000, -1000),
            (1000, 0),
        ],
    }
    if sample_name not in sample_options:
        all_samples = ", ".join(sample_options.keys())
        raise ValueError(
            f"{sample_name} is not a valid sample name. Valid names : {all_samples}"
        )
    return sample_options[sample_name]


if __name__ == "__main__":
    profile_and_save_plot_for_example_smart_spiral()
