import tempfile
import os
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
    x_pos = random.randint(-100, 100)
    y_pos = random.randint(-100, 100)
    filename = f"image_{x_pos}_{y_pos}.jpg"
    filepath = os.path.join(scan_dir.images_dir, filename)
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
    fake_file = scan_dir_manager.get_file_from(scan_name, "foo.zip")
    assert fake_file == os.path.join(scan_path, "foo.zip")
    # But this is none if we check it exists
    fake_file = scan_dir_manager.get_file_from(scan_name, "foo.zip", check_exists=True)
    assert fake_file is None

    # Get the path of another fake file
    fake_file = scan_dir_manager.get_file_from_img_dir(scan_name, "bar.img")
    assert fake_file == os.path.join(scan_im_dir, "bar.img")
    # But this is none if we check it exists
    fake_file = scan_dir_manager.get_file_from_img_dir(
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

    # Add a fake scan and check this is recognised as a stitch not a scan image
    _add_fake_file(scan_dir, "fake_scan_0001_stitched.jpg", in_im_dir=True)
    info = scan_dir.scan_info()
    assert info.number_of_images == 17
    assert info.stitch_available


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


def test_creating_scan_dir_for_missing_scan():
    """Check creating ScanDirectory object for a dir that doesn't exist fails."""
    _clear_scan_dir()
    with pytest.raises(FileNotFoundError):
        ScanDirectory(BASE_SCAN_DIR, "not_real_0001")


def test_none_returned_for_missing_images_dir():
    """None should be returned for image dir path if images dir does not exist.

    By default images directories are created at the same time the scan directory
    is created. However, edge cases such as problems in deletions, microscopes
    with older scans on, etc can cause and empty scan directory, so it is handled
    explicitly.
    """
    _clear_scan_dir()
    os.makedirs(os.path.join(BASE_SCAN_DIR, "fake_scan_0001"))
    scan_dir = ScanDirectory(BASE_SCAN_DIR, "fake_scan_0001")
    assert scan_dir.images_dir is None
    # Also check that get scan files returns and empty list
    assert scan_dir.get_scan_files() == []


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
