"""
Tests that check that a tuning file can be reloaded
"""

import os

import pytest
from picamera2 import Picamera2

from openflexure_microscope_server.things.camera import (
    picamera_recalibrate_utils as recalibrate_utils,
)


MODEL = Picamera2.global_camera_info()[0]["Model"]


def load_default_tuning():
    """
    Return the default tuning file for the connected camera.
    """
    fname = f"{MODEL}.json"
    return Picamera2.load_tuning_file(fname)


def generate_bad_tuning():
    """
    Return a tuning file with an invalid version number to force an error when loaded.
    """
    default_tuning = load_default_tuning()
    bad_tuning = default_tuning.copy()
    bad_tuning["version"] = 999
    return bad_tuning


def print_tuning(read_file: bool = False):
    """
    Print the path of the default tuning file from the the environment variable.

    :param read_file: Boolean, set true to also print the file contents.

    This is useful for debugging. As pytest suppresses the printing by default the
    -s option is needed when running pytest to see this.
    """
    key = "LIBCAMERA_RPI_TUNING_FILE"
    if key in os.environ:
        print(f"Tuning file environment variable: {os.environ[key]}")
        if read_file:
            with open(os.environ[key], "r") as f:
                print(f.read())
    else:
        print("Tuning file environment variable not set")


def _test_bad_tuning_after_good_tuning(configure: bool = False):
    """
    Load the default tuning file into the camera, re-load with a broken tuning file,
    check it errors. Finally check the default tuning file will load again afterwards.

    :param configure: Boolean, set true to configure the camera on initial loading

    This test checks that:
    recalibrate_utils.recreate_camera_manager() is working as expected. As the default
    PiCamera2 behaviour does not expect the tuning file to be reloaded.
    """
    bad_tuning = generate_bad_tuning()
    default_tuning = load_default_tuning()
    print_tuning()
    print("opening camera with default tuning")
    with Picamera2(tuning=default_tuning) as cam:
        print_tuning()
        if configure:
            cam.configure(cam.create_preview_configuration())
    del cam
    recalibrate_utils.recreate_camera_manager()
    print(f"Opening camera with bad tuning - ['version'] = {bad_tuning['version']}")
    with pytest.raises(IndexError):
        # The bad version should cause a problem
        cam = Picamera2(tuning=bad_tuning)
        print_tuning()
        print("Success (not expected)!")
        del cam
    recalibrate_utils.recreate_camera_manager()
    with Picamera2(tuning=default_tuning) as cam:
        # Reload the camera with working tuning, or it will stop responding
        # and fail future tests
        pass
    del cam


# Note: The tests below are marked with
# @pytest.mark.filterwarnings("ignore: Exception ignored")
# as the picamera will throw an exception ignored warning when deleting
# the picamera object. This is expected

# The 2 pairs of repeated identical tests exist because pytest only
# starts once, and so by running the test more than one time checks
# that the camera can be initialised multiple times without restarting
# python.


@pytest.mark.filterwarnings("ignore: Exception ignored")
def test_bad_tuning_after_good_tuning_noconfigure():
    _test_bad_tuning_after_good_tuning(False)


@pytest.mark.filterwarnings("ignore: Exception ignored")
def test_bad_tuning_after_good_tuning_configure():
    _test_bad_tuning_after_good_tuning(True)


@pytest.mark.filterwarnings("ignore: Exception ignored")
def test_bad_tuning_after_good_tuning_noconfigure2():
    _test_bad_tuning_after_good_tuning(False)


@pytest.mark.filterwarnings("ignore: Exception ignored")
def test_bad_tuning_after_good_tuning_configure2():
    _test_bad_tuning_after_good_tuning(True)
