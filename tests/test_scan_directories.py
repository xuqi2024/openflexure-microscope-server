import tempfile
import os
import math
import shutil
import logging
import random
import time
from collections import namedtuple

import pytest

from openflexure_microscope_server.scan_directories import (
    ScanDirectoryManager,
    ScanDirectory,
    ScanInfo,
    get_files_in_zip,
    NotEnoughFreeSpaceError,
)

# A global logger to pass in as an Invocation Logger
LOGGER = logging.getLogger("mock-invocation_logger")

# Use our own dir in the root temp dir not a dynamically generated one so we
# have some control of when it is deleted
BASE_SCAN_DIR = os.path.join(tempfile.gettempdir(), "scans")


def _clear_scan_dir() -> None:
    """Delete the scan dir"""
    if os.path.exists(BASE_SCAN_DIR):
        shutil.rmtree(BASE_SCAN_DIR)


def _add_fake_image(scan_dir: ScanDirectory) -> None:
    """Make a fake image on disk in the scan directory"""
    unique = False
    while not unique:
        x_pos = random.randint(-10000, 10000)
        y_pos = random.randint(-10000, 10000)
        filename = f"image_{x_pos}_{y_pos}.jpg"
        filepath = os.path.join(scan_dir.images_dir, filename)
        unique = not os.path.exists(filepath)
    with open(filepath, "w") as f_obj:
        f_obj.write("fake")


def _add_fake_file(
    scan_dir: ScanDirectory, filename: str, in_im_dir: bool = False
) -> None:
    """Make a fake file on disk in the scan directory.

    :param in_im_dir: Boolean, if set True the fake file is created in the images
    directory of the scan not the root directory.
    """
    if in_im_dir:
        filepath = os.path.join(scan_dir.images_dir, filename)
    else:
        filepath = os.path.join(scan_dir.dir_path, filename)
    with open(filepath, "w") as f_obj:
        f_obj.write("fake")


def _make_fake_dzi(scan_dir: ScanDirectory, n_layers: int = 8) -> None:
    """Create a fake DZI in a scan

    :param n_layers: The number of layers of tiles. I.e. tile directories numbered
        0...(n_layers-1) will be created. Default 8
    """

    # Add an a dzi image
    dzi_fname = scan_dir.name + ".dzi"
    dzi_path = os.path.join(scan_dir.images_dir, dzi_fname)
    with open(dzi_path, "w") as f_obj:
        f_obj.write("This should be xml")

    # and the directory for the dzi tiles
    dzi_tile_dir = scan_dir.name + "_files"
    dzi_tile_dir_path = os.path.join(scan_dir.images_dir, dzi_tile_dir)
    os.makedirs(dzi_tile_dir_path)

    # this directory then contains a directories numbered from 0-n
    for i in range(n_layers):
        layer_dir_path = os.path.join(dzi_tile_dir_path, str(i))
        os.makedirs(layer_dir_path)

        # Number of images (in each axis) in this layer. Number of tiles doubles each
        # layer, but the first few layers always have 1 image.
        n_ims = math.ceil(2 ** (i - 4))
        for x_index in range(n_ims):
            for y_index in range(n_ims):
                tile_name = f"{x_index}_{y_index}.jpg"
                tile_path = os.path.join(layer_dir_path, tile_name)
                with open(tile_path, "w") as f_obj:
                    f_obj.write("This would normally be jpeg data")


def test_basic_directory_operations():
    """Test some basic operations

    Test some basic operations, including:
    - ScanDirectoryManager creates a scan directory
    - For a fake (dummy) scan, a path can be created and retrieved
    - For a fake (dummy) file, a path can be created and retrieved (for both a .zip and .img file)
    - When a scan directory is created, the directory exists as does the image directory
    - Scan directories can be deleted and scans can be cleared
    """
    _clear_scan_dir()
    assert not os.path.isdir(BASE_SCAN_DIR)
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    # Check it makes the scan directory
    assert os.path.isdir(BASE_SCAN_DIR)

    # Considering a fake scan
    scan_name = "fake_scan_0001"
    scan_path = os.path.join(BASE_SCAN_DIR, scan_name)
    scan_im_dir = os.path.join(BASE_SCAN_DIR, scan_name, "images")

    # It doesn't exist but we can check its paths
    assert not scan_dir_manager.exists(scan_name)
    assert not os.path.isdir(scan_path)
    assert scan_dir_manager.path_for(scan_name) == scan_path
    assert scan_dir_manager.img_dir_for(scan_name) == scan_im_dir

    # Get the path of a fake file
    fake_file = scan_dir_manager.get_file_path_from(scan_name, "foo.zip")
    assert fake_file == os.path.join(scan_path, "foo.zip")
    # But this is none if we check it exists
    fake_file = scan_dir_manager.get_file_path_from(
        scan_name, "foo.zip", check_exists=True
    )
    assert fake_file is None

    # Get the path of another fake file
    fake_file = scan_dir_manager.get_file_path_from_img_dir(scan_name, "bar.img")
    assert fake_file == os.path.join(scan_im_dir, "bar.img")
    # But this is none if we check it exists
    fake_file = scan_dir_manager.get_file_path_from_img_dir(
        scan_name, "bar.img", check_exists=True
    )
    assert fake_file is None

    # Create the dir
    scan_dir = scan_dir_manager.new_scan_dir("fake_scan")
    # This returns a ScanDirectory object
    assert isinstance(scan_dir, ScanDirectory)
    # The directory now exists as does the image directory
    assert scan_dir_manager.exists(scan_name)
    assert os.path.isdir(scan_path)
    assert os.path.isdir(scan_im_dir)

    # Test cleanup. Delete the created scan and scan directory
    scan_dir_manager.delete_scan(scan_name)
    assert not scan_dir_manager.exists(scan_name)
    assert not os.path.isdir(scan_path)


def test_scan_sequence_and_listing():
    """
    Check created scans are added in order and listed correctly
    """
    _clear_scan_dir()
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    # Make 4 scans
    scan_dir_manager.new_scan_dir("fake_scan")
    scan_dir_manager.new_scan_dir("fake_scan")
    scan_dir_manager.new_scan_dir("fake_scan")
    scan_dir_manager.new_scan_dir("fake_scan")

    # Check they exist and are numbered sequentially
    all_scans = scan_dir_manager.all_scans
    assert len(set(all_scans)) == 4
    assert "fake_scan_0001" in all_scans
    assert "fake_scan_0002" in all_scans
    assert "fake_scan_0003" in all_scans
    assert "fake_scan_0004" in all_scans

    # Check scan data can be read for all of them
    # (more detailed scan_info tests below)
    all_scan_info = scan_dir_manager.all_scans_info()
    for scan_info in all_scan_info:
        assert isinstance(scan_info, ScanInfo)
        assert scan_info.name.startswith("fake_scan_000")
        assert scan_info.number_of_images == 0


def test_scan_name_non_sequential():
    """
    Check created scans is the correct name if the directories
    are not sequential
    """
    _clear_scan_dir()
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0001"))
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0002"))
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0003"))
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0005"))
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0007"))
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0011"))
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)

    scan_dir = scan_dir_manager.new_scan_dir("fake_scan")
    assert scan_dir.name == "fake_scan_0012"

    all_scans = scan_dir_manager.all_scans
    assert len(set(all_scans)) == 7
    assert "fake_scan_0001" in all_scans
    assert "fake_scan_0002" in all_scans
    assert "fake_scan_0003" in all_scans
    assert "fake_scan_0005" in all_scans
    assert "fake_scan_0007" in all_scans
    assert "fake_scan_0011" in all_scans
    assert "fake_scan_0012" in all_scans


def test_all_scan_names_taken():
    """
    If the next sequential scan name needs more than 4 digits check error is thrown.
    """
    _clear_scan_dir()
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_9999"))
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    with pytest.raises(FileExistsError):
        scan_dir_manager.new_scan_dir("fake_scan")


def test_no_scan_names_given():
    """
    Check correct default scan name is used if empty string is given
    """
    _clear_scan_dir()
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    scan_dir = scan_dir_manager.new_scan_dir("")
    assert scan_dir.name == "scan_0001"


def test_scan_info():
    """Test the scan info is correct even using fake scan data"""
    _clear_scan_dir()
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    scan_dir = scan_dir_manager.new_scan_dir("fake_scan")

    for i in range(17):
        _add_fake_image(scan_dir)
    info = scan_dir.scan_info()
    now = time.time()

    assert info.name == "fake_scan_0001"
    # Created and modified in the last 5 seconds
    assert now - 5 < info.created < now
    assert now - 5 < info.modified < now
    assert info.number_of_images == 17
    assert not info.stitch_available
    assert info.dzi is None

    # Add a fake stitched images and check this is recognised as a stitch not
    # a scan image
    _add_fake_file(scan_dir, "fake_scan_0001_stitched.jpg", in_im_dir=True)
    info = scan_dir.scan_info()
    assert info.number_of_images == 17
    assert info.stitch_available


def test_get_final_stitch():
    """Check that the final stitch can be retrieved"""
    _clear_scan_dir()
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    scan_dir = scan_dir_manager.new_scan_dir("fake_scan")

    # Create some scan images files
    for i in range(17):
        _add_fake_image(scan_dir)

    # No scans, so None should be returned, from both manager and scan dir
    assert scan_dir_manager.get_final_stitch_path(scan_dir.name) is None
    assert scan_dir.get_final_stitch_name() is None

    fake_scan_name = "fake_scan_0001_stitched.jpg"
    fake_scan_path = scan_dir_manager.get_file_path_from_img_dir(
        scan_name=scan_dir.name,
        filename="fake_scan_0001_stitched.jpg",
        check_exists=False,
    )
    # Add a fake scan
    _add_fake_file(scan_dir, fake_scan_name, in_im_dir=True)
    # Manager returns full path
    assert scan_dir_manager.get_final_stitch_path(scan_dir.name) == fake_scan_path
    # ScanDirectory object returns just the filename
    assert scan_dir.get_final_stitch_name() == fake_scan_name


def test_empty_scan_info():
    """Test the scan info is correct even if the scan is empty"""
    _clear_scan_dir()
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    scan_dir = scan_dir_manager.new_scan_dir("fake_scan")

    info = scan_dir.scan_info()
    now = time.time()

    assert info.name == "fake_scan_0001"
    # Created and modified in the last 5 seconds
    assert now - 5 < info.created < now
    assert now - 5 < info.modified < now
    assert info.number_of_images == 0
    assert not info.stitch_available
    assert info.dzi is None


def test_zipping_scan_data():
    """Test zipping the scan images with fake image data"""

    # Run twice, once calling the ScanDirectory directly,
    # Once calling the ScanDirectoryManager
    for caller in ["scan_dir", "manager"]:
        _clear_scan_dir()
        scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
        scan_dir = scan_dir_manager.new_scan_dir("fake_scan")

        # Create 21 fake scan images, a fake stitch, and a fake zip
        for i in range(21):
            _add_fake_image(scan_dir)
        _add_fake_file(scan_dir, "fake_scan_0001_stitched.jpg", in_im_dir=True)
        _add_fake_file(scan_dir, "zipfile.zip")

        # This fake dzi should have loads of images. The DZI should not be zipped!
        _make_fake_dzi(scan_dir)

        # zip the directory without setting as the final version. It should only
        # zip the 21 scan images
        if caller == "scan_dir":
            zip_fname = scan_dir.zip_files()
        else:
            zip_fname = scan_dir_manager.zip_scan("fake_scan_0001")
        zip_files = get_files_in_zip(zip_fname)
        assert len(set(zip_files)) == 21

        # Zip again with final version on and there should be 22 images
        if caller == "scan_dir":
            scan_dir.zip_files(final_version=True)
        else:
            scan_dir_manager.zip_scan("fake_scan_0001", final_version=True)
        zip_files = get_files_in_zip(zip_fname)
        assert len(set(get_files_in_zip(zip_fname))) == 22
        # Check the zips are not in the zip
        for file in zip_files:
            assert not file.endswith(".zip")
            assert not file.endswith(".dzi")


def test_all_files():
    """Test all_files returns the path, and respects skipped directories"""
    _clear_scan_dir()
    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    scan_dir = scan_dir_manager.new_scan_dir("fake_scan")
    # This fake dzi should have loads of images. The DZI should not be zipped!
    _make_fake_dzi(scan_dir)
    all_files = scan_dir.all_files()

    # As standard for 8 layers there are 89 jpegs and 1 dzi file.
    assert len(set(all_files)) == 90
    assert len(all_files) == 90
    dzi_file = None
    # Check all files exist
    for file in all_files:
        assert os.path.exists(os.path.join(scan_dir.dir_path, file))
        if file.endswith(".dzi"):
            # There is only 1 dzi file, so this should be None
            assert dzi_file is None
            dzi_file = file
    # Once loop is complete there should be a dzi file
    assert dzi_file is not None
    # Get the dzi tile directory name
    dzi_dir = os.path.basename(dzi_file[:-4] + "_files")

    # Get all files skipping the dzi tile directory
    all_files = scan_dir.all_files(skip_dirs=dzi_dir)
    # There is now only one file
    assert len(all_files) == 1
    # It is the DZI file
    assert all_files[0] == dzi_file


def test_creating_scan_dir_for_missing_scan():
    """Check creating ScanDirectory object for a dir that doesn't exist fails."""
    _clear_scan_dir()
    with pytest.raises(FileNotFoundError):
        ScanDirectory("not_real_0001", BASE_SCAN_DIR)


def test_none_returned_for_missing_images_dir():
    """None should be returned for image dir path if images dir does not exist.

    By default images directories are created at the same time the scan directory
    is created. However, edge cases such as problems in deletions, microscopes
    with older scans on, etc can cause and empty scan directory, so it is handled
    explicitly.
    """
    _clear_scan_dir()
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0001"))
    scan_dir = ScanDirectory("fake_scan_0001", BASE_SCAN_DIR)
    assert scan_dir.images_dir is None
    # Also check that get scan files returns and empty list
    assert scan_dir.get_scan_files() == []


def test_extracting_files():
    """Test the private _find_files method of ScanDirectories

    Add files to directory and check expected returns.
    """
    _clear_scan_dir()
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0001", "images"))
    scan_dir = ScanDirectory("fake_scan_0001", BASE_SCAN_DIR)

    # Starting all lists should be empty
    scan_files = scan_dir.get_scan_files()
    assert scan_dir._extract_scan_images(scan_files) == []
    assert scan_dir._extract_final_stitches(scan_files) == []
    assert scan_dir._extract_dzi_files(scan_files) == []

    # Add a number of images
    for i in range(2321):
        _add_fake_image(scan_dir)

    scan_files = scan_dir.get_scan_files()
    assert len(set(scan_dir._extract_scan_images(scan_files))) == 2321
    assert len(set(scan_dir._extract_final_stitches(scan_files))) == 0
    assert len(set(scan_dir._extract_dzi_files(scan_files))) == 0

    # Add and a stitched image
    _add_fake_file(scan_dir, "fake_scan_0001_stitched.jpg", in_im_dir=True)

    scan_files = scan_dir.get_scan_files()
    assert len(set(scan_dir._extract_scan_images(scan_files))) == 2321
    assert len(set(scan_dir._extract_final_stitches(scan_files))) == 1
    assert len(set(scan_dir._extract_dzi_files(scan_files))) == 0

    _make_fake_dzi(scan_dir)

    # check totals are still correct after adding a dzi with lots of tiles.
    scan_files = scan_dir.get_scan_files()
    scan_images = scan_dir._extract_scan_images(scan_files)
    stitches = scan_dir._extract_final_stitches(scan_files)
    dzi_files = scan_dir._extract_dzi_files(scan_files)
    assert len(set(scan_images)) == 2321
    assert len(set(stitches)) == 1
    assert len(set(dzi_files)) == 1

    # And check the names are as expected
    assert stitches[0] == "fake_scan_0001_stitched.jpg"
    assert dzi_files[0] == "fake_scan_0001.dzi"


DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])


@pytest.mark.parametrize("free_space", [500_000_001, 700_000_000, 5_000_000_000])
def test_disk_not_full(mocker, free_space):
    """Check no error thrown if disk has over 500MB of space"""
    total_space = 16_000_000_000
    # Mock the disk_usage
    mocker.patch(
        "shutil.disk_usage",
        return_value=DiskUsage(
            total=total_space, used=total_space - free_space, free=free_space
        ),
    )

    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    scan_dir_manager.check_free_disk_space()


@pytest.mark.parametrize("free_space", [100_000_000, 499_999_999])
def test_disk_full(mocker, free_space):
    """Check error thrown if disk has under 500MB of space"""
    total_space = 16_000_000_000
    # Mock the disk_usage
    mocker.patch(
        "shutil.disk_usage",
        return_value=DiskUsage(
            total=total_space, used=total_space - free_space, free=free_space
        ),
    )

    scan_dir_manager = ScanDirectoryManager(BASE_SCAN_DIR)
    with pytest.raises(NotEnoughFreeSpaceError):
        scan_dir_manager.check_free_disk_space()
