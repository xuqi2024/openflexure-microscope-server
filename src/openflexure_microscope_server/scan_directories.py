"""Functionality to manage file system operations for scan directories."""

from typing import Optional
import os
import re
import shutil
import zipfile

from pydantic import BaseModel

IMG_DIR_NAME = "images"
SCAN_ZERO_PAD_DIGITS = 4

STITCH_REGEX = re.compile(r"stitched\.jpe?g$")
IMAGE_REGEX = re.compile(r"-?[0-9]+_-?[0-9]+\.jpe?g$")


class NotEnoughFreeSpaceError(IOError):
    """An exception raised if there is not enough free space on disk to scan."""


class ScanInfo(BaseModel):
    """Summary information about a scan folder."""

    name: str
    created: float
    modified: float
    number_of_images: int
    stitch_available: bool
    dzi: Optional[str]


class ScanDirectoryManager:
    """A class for managing interactions with scan directories."""

    _base_scan_dir: str

    def __init__(self, base_scan_dir: str):
        """Initialise the scan directory manager.

        :param base_scan_dir: Path of the directory that holds all scans.
        """
        self._base_scan_dir = base_scan_dir
        if not os.path.exists(self._base_scan_dir):
            os.makedirs(self._base_scan_dir)

    @property
    def base_dir(self) -> str:
        """The base directory scans are saved to."""
        return self._base_scan_dir

    def exists(self, scan_name: str) -> bool:
        """Return True if scan of this name exists on disk."""
        return os.path.isdir(self.path_for(scan_name))

    def path_for(self, scan_name: str) -> str:
        """Return the path for a given scan name.

        Returns the path even if it doesn't exist
        """
        return os.path.join(self._base_scan_dir, scan_name)

    def img_dir_for(self, scan_name: str) -> str:
        """Return the path for the image dir for a given scan name.

        Returns the path even if it doesn't exist
        """
        return os.path.join(self._base_scan_dir, scan_name, IMG_DIR_NAME)

    def get_file_path_from(
        self, scan_name: str, filename: str, check_exists: bool = False
    ) -> Optional[str]:
        """Return the full file path for the file within a scan directory.

        If check_exists is True then None will be returned if the file does
        not exist.
        """
        file_path = os.path.join(self.path_for(scan_name), filename)
        if check_exists:
            if not os.path.exists(file_path):
                return None
        return file_path

    def get_file_path_from_img_dir(
        self, scan_name: str, filename: str, check_exists: bool = False
    ) -> Optional[str]:
        """Return the full file path for the file within a scan directory.

        If check_exists is True, None is returned if the file does not exist. If False
        then the path is returned anyway
        """
        file_path = os.path.join(self.img_dir_for(scan_name), filename)
        if check_exists:
            if not os.path.exists(file_path):
                return None
        return file_path

    def get_final_stitch_path(self, scan_name: str) -> Optional[str]:
        """Return the file full path for the final stitch.

        If no final stitch is found, return None
        """
        stitch_fname = ScanDirectory(scan_name, self.base_dir).get_final_stitch_name()
        if stitch_fname is None:
            return None
        return self.get_file_path_from_img_dir(scan_name, stitch_fname)

    @property
    def all_scans(self) -> list[str]:
        """Return a list of the scan names in the base directory."""
        return [f.name for f in os.scandir(self._base_scan_dir) if f.is_dir()]

    def all_scans_info(self) -> list[ScanInfo]:
        """Return a lists of ScanInfo objects for each scan."""
        all_info: list[ScanInfo] = []
        for scan_name in self.all_scans:
            all_info.append(ScanDirectory(scan_name, self.base_dir).scan_info())
        return all_info

    def _unique_scan_name(self, scan_name: str) -> str:
        """Get the next unique scan name starting with the given name.

        For more explanation on the scan naming see `new_scan_dir`
        """
        # A regex with the scan name and a group for the numbers
        scan_regex = re.compile(
            "^" + scan_name + "_([0-9]{" + str(SCAN_ZERO_PAD_DIGITS) + "})$"
        )

        matching_scans = [scan for scan in self.all_scans if scan_regex.match(scan)]
        if not matching_scans:
            scan_num = 1
        else:
            last_matching_scan = sorted(matching_scans)[-1]
            # Get the first group from the regex, turn to int, and add 1
            scan_num = int(scan_regex.match(last_matching_scan)[1]) + 1

        # Set a sensible limit for the number of scans of one name
        # based on our zero padding.
        max_scan_no = 10**SCAN_ZERO_PAD_DIGITS - 1

        if scan_num > max_scan_no:
            raise FileExistsError(
                "Could not create a new scan folder: all names in use!"
            )

        return f"{scan_name}_{scan_num:0{SCAN_ZERO_PAD_DIGITS}d}"

    def new_scan_dir(self, scan_name: str) -> "ScanDirectory":
        """Get a unique name for this scan and create a directory for it.

        The scan will be named ``{scan_name}_0001`` where the number is
        zero-padded to be SCAN_ZERO_PAD_DIGITS digits long (to allow correct sorting if the
        scans are ordered alphanumerically).

        Creates a new empty folder, into which scans are saved

        Returns the a ScanDirectory object
        """
        # if no scan name is set set to "scan". This done here as empty strings
        # get passed in otherwise.
        if not scan_name:
            scan_name = "scan"

        full_scan_name = self._unique_scan_name(scan_name)

        os.makedirs(self.path_for(full_scan_name))
        os.makedirs(self.img_dir_for(full_scan_name))
        return ScanDirectory(full_scan_name, self.base_dir)

    def delete_scan(self, scan_name: str) -> None:
        """Delete a scan."""
        shutil.rmtree(self.path_for(scan_name))

    def zip_scan(self, scan_name: str, final_version: bool = False) -> "ScanDirectory":
        """Zips any images from the scan not yet zipped, return full path to zip.

        ``final_version`` Set true to stitch all files not just the scan images
        this should only be done at the end as it is not possible to update a file
        in a zip.
        """
        return ScanDirectory(scan_name, self.base_dir).zip_files(final_version)

    def check_free_disk_space(self, min_space: int = 500000000) -> None:
        """Raise an exception if there is not enough free disk space to continue scanning.

        :param min_space: the minimum space required in bytes.
            Default = 500,000,000 (500MB)

        :raises NotEnoughFreeSpaceError: if the remaining storage is below min_space
        """
        disk_usage = shutil.disk_usage(self._base_scan_dir)
        if disk_usage.free < min_space:
            raise NotEnoughFreeSpaceError(
                "There is not enough free disk space to continue. "
                f"(Required: {min_space >> 20}MB. Free: {disk_usage.free >> 20}MB)."
            )


class ScanDirectory:
    """A class for handling interactions with scan directories."""

    _name: str
    _base_scan_dir: str

    def __init__(self, name: str, base_scan_dir: str):
        """Initialise the scan directory.

        :param name: the name of the scan (the scan directory basename).
        :param base_scan_dir: Path of the directory that holds all scans.
        """
        self._name = name
        self._base_scan_dir = base_scan_dir
        if not os.path.isdir(self.dir_path):
            raise FileNotFoundError(
                f"The scan directory {self.dir_path} cannot be found"
            )

    @property
    def name(self) -> str:
        """The name of the scan."""
        return self._name

    @property
    def dir_path(self) -> str:
        """The full path to the scan directory."""
        return os.path.join(self._base_scan_dir, self._name)

    @property
    def images_dir(self) -> Optional[str]:
        """The path to the images directory.

        None is returned if no images directory was created.
        """
        im_path = os.path.join(self.dir_path, IMG_DIR_NAME)
        if os.path.isdir(im_path):
            return im_path
        return None

    @property
    def created_time(self) -> float:
        """The time the directory was created on disk."""
        return os.path.getctime(self.dir_path)

    def get_scan_files(self):
        """Return a list of the files in the images dir."""
        if self.images_dir is None:
            return []
        return os.listdir(self.images_dir)

    def _extract_scan_images(self, file_list: list[str]):
        """Extract files which match the naming convention for scan images.

        :param file_list: The list of files to search. Normally this would be
            ``self.get_scan_files()``

        :returns: The list of files that match the naming convention for scan images
        """
        return [i for i in file_list if IMAGE_REGEX.search(i)]

    def _extract_final_stitches(self, file_list: list[str]):
        """Extract files which match the naming convention for final stitches.

        :param file_list: The list of files to search.

        :returns: The list of files that match the naming convention for final stitches
        """
        return [i for i in file_list if STITCH_REGEX.search(i)]

    def _extract_dzi_files(self, file_list: list[str]):
        """Extract files which match the naming convention for dzi_files.

        :param file_list: The list of files to search.

        :returns: The list of files that match the naming convention for dzi_files
        """
        return [i for i in file_list if i.endswith("dzi")]

    def get_final_stitch_name(self) -> Optional[str]:
        """Return the filename for the final stitch (in the images dir).

        If no final stitch is found, return None
        """
        stitches = self._extract_final_stitches(self.get_scan_files())
        if not stitches:
            return None
        return stitches[0]

    def get_modified_time(self) -> float:
        """Return the modified time of the directory."""
        return max(os.stat(root).st_mtime for root, _, _ in os.walk(self.dir_path))

    def scan_info(self) -> ScanInfo:
        """Return the information for the scan directory as a ScanInfo object."""
        scan_files = self.get_scan_files()
        scan_images = self._extract_scan_images(scan_files)
        stitches = self._extract_final_stitches(scan_files)
        dzi_files = self._extract_dzi_files(scan_files)
        number_of_images = len(scan_images)
        stitch_available = len(stitches) > 0
        dzi = None if not dzi_files else str(dzi_files[0])

        return ScanInfo(
            name=self.name,
            created=self.created_time,
            modified=self.get_modified_time(),
            number_of_images=number_of_images,
            stitch_available=stitch_available,
            dzi=dzi,
        )

    def all_files(self, skip_dirs: Optional[list[str]] = None) -> list[str]:
        """Return a list of all files in the scan dir relative to the dir.

        :param skip_dirs: Skip any file in a directory that is on this list. The list
            should be the basename of the directory. e.g. "scan_0001_files" not
            "images/scan_0001_files"
        """
        if skip_dirs is None:
            skip_dirs = []
        files = []
        for file_root, dirs, filenames in os.walk(self.dir_path, topdown=True):
            # Skip any skipped directories.
            # Note: we must use slice assignment to edit in place.
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for filename in filenames:
                full_path = os.path.join(file_root, filename)
                files.append(os.path.relpath(full_path, self.dir_path))
        return files

    def zip_files(self, final_version: bool = False) -> str:
        """Zips any images from the scan not yet zipped, return full path to zip.

        ``final_version`` Set true to stitch all files not just the scan images
        this should only be done at the end as it is not possible to update a file
        in a zip.
        """
        zip_fname = os.path.join(self.dir_path, "images.zip")

        if os.path.isfile(zip_fname):
            # get a list of files in the existing zip
            zip_files = get_files_in_zip(zip_fname)
        else:
            zip_files = []

        # For each `filename.dzi` we need to skip the `filename_files` directory
        dzi_files = self._extract_dzi_files(self.get_scan_files())
        dzi_dirs = [dzi[:-4] + "_files" for dzi in dzi_files]

        with zipfile.ZipFile(zip_fname, mode="a") as scan_zip:
            for file in self.all_files(skip_dirs=dzi_dirs):
                # Don't zip zipfiles, dzi files, or files already in the zip
                if file.endswith((".zip", ".dzi")) or file in zip_files:
                    continue
                # If this is not the final version, then only zip image files.
                if not final_version and not IMAGE_REGEX.search(file):
                    continue

                scan_zip.write(os.path.join(self.dir_path, file), arcname=file)
        return zip_fname


def get_files_in_zip(zip_path):
    """List the relative paths of all files and folders in the zip folder specified."""
    scan_zip = zipfile.ZipFile(zip_path)
    return [os.path.normpath(i) for i in scan_zip.namelist()]
