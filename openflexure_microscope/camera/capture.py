import uuid
import io
import os
import shutil
import glob
import datetime
import yaml
import logging
from PIL import Image
import atexit

from openflexure_microscope.camera import piexif
from openflexure_microscope.camera.piexif._exceptions import InvalidImageDataError


PIL_FORMATS = ["JPG", "JPEG", "PNG", "TIF", "TIFF"]
EXIF_FORMATS = ["JPG", "JPEG", "TIF", "TIFF"]
THUMBNAIL_SIZE = (200, 150)


def pull_usercomment_dict(filepath):
    """
    Reads UserComment Exif data from a file, and returns the contained bytes as a dictionary.
    Args:
        filepath: Path to the Exif-containing file
    """
    try:
        exif_dict = piexif.load(filepath)
    except InvalidImageDataError:
        logging.error("Invalid data at {}. Skipping.".format(filepath))
        return None
    if "Exif" in exif_dict and 37510 in exif_dict["Exif"]:
        return yaml.load(exif_dict["Exif"][37510].decode())
    else:
        return None


def make_file_list(directory, formats):
    files = []
    for fmt in formats:
        files.extend(
            glob.glob("{}/**/*.{}".format(directory, fmt.lower()), recursive=True)
        )

    logging.info("{} capture files found on disk".format(len(files)))

    return files


def build_captures_from_exif(capture_path):
    global EXIF_FORMATS

    logging.debug("Reloading captures from {}...".format(capture_path))
    files = make_file_list(capture_path, EXIF_FORMATS)
    captures = []

    for f in files:
        logging.debug("Reloading capture {}...".format(f))
        exif = pull_usercomment_dict(f)
        if exif:
            capture = capture_from_exif(f, exif)
            captures.append(capture)
        else:
            logging.error("Invalid data at {}. Skipping.".format(f))

    logging.info("{} capture files successfully reloaded".format(len(captures)))

    return captures


def capture_from_exif(path, exif_dict):
    """
    Creates an instance of CaptureObject from a dictionary of capture information.
    This is used when reloading the API server, to restore captures created in the 
    previous session.

    Args:
        exif_dict (dict): Dictionary containing capture information
    """

    # Create a placeholder capture
    capture = CaptureObject(filepath=path)

    # Build file path information
    capture.split_file_path(capture.file)

    # Populate capture parameters
    capture.id = exif_dict["id"]

    capture.timestring = exif_dict["time"]
    capture.format = exif_dict["format"]

    capture._metadata = exif_dict["custom"]
    capture.tags = exif_dict["tags"]

    return capture


class CaptureObject(object):
    """
    StreamObject used to store and process on-disk capture data, and metadata.
    Serves to simplify modifying properties of on-disk capture data.

    Attributes:
        timestring (str): Timestring of capture creation time
        _metadata (dict): Dictionary of custom metadata to be included in metadata file
        tags (list): List of tags. Essentially just as extra custom metadata field, but useful for quick organisation
        filefolder (str): Folder in which the capture file will be stored
        filename (str): Full name of the capture file
        basename (str): Filename of the capture, without a file extension
        format (str): Format of the capture data

    """

    def __init__(self, filepath) -> None:
        """Create a new StreamObject, to manage capture data."""

        # Store a nice ID
        self.id = uuid.uuid4().hex  #: str: Unique capture ID
        logging.debug("Created StreamObject {}".format(self.id))
        self.timestring = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Create file name. Default to UUID
        self.file = filepath
        self.split_file_path(self.file)

        # Dictionary for storing custom metadata
        self._metadata = {}

        # List for storing tags
        self.tags = []

        # Thumbnail (populated only for PIL captures)
        self.thumb_bytes = None

    def open(self, mode):
        return open(self.file, mode)

    def split_file_path(self, filepath):
        """
        Take a full file path, and split it into separated class properties.

        Args:
            filepath (str): String of the full file path, including file format extension
        """
        # Split the full file path into a folder and a filename
        self.filefolder, self.filename = os.path.split(filepath)
        # Split the filename out from it's file extension
        self.basename = os.path.splitext(self.filename)[0]
        self.format = self.filename.split(".")[-1]

        # Create folder and file
        if not os.path.exists(self.filefolder):
            os.makedirs(self.filefolder)

    @property
    def exists(self) -> bool:
        """Check if capture data file exists on disk."""
        if os.path.isfile(self.file):
            return True
        else:
            return False

    # HANDLE TAGS
    def put_tags(self, tags: list):
        """
        Add a new tag to the ``tags`` list attribute.

        Args:
            tags (list): List of tags to be added
        """
        for tag in tags:
            if tag not in self.tags:
                self.tags.append(tag)

        self.save_metadata()

    def delete_tag(self, tag: str):
        """
        Remove a tag from the ``tags`` list attribute, if it exists.

        Args:
            tag (str): Tag to be removed
        """
        if tag in self.tags:
            self.tags = [new_tag for new_tag in self.tags if new_tag != tag]

        self.save_metadata()

    # HANDLE METADATA

    def put_metadata(self, data: dict) -> None:
        """
        Merge metadata from a passed dictionary into the capture metadata, and saves.

        Args:
            data (dict): Dictionary of metadata to be added
        """
        self._metadata.update(data)
        self.save_metadata()

    def save_metadata(self) -> None:
        """
        Save metadata to exif, if supported
        """
        global EXIF_FORMATS

        if self.format.upper() in EXIF_FORMATS and self.exists:
            logging.debug("Writing exif data to capture file")
            # Extract current Exif data
            exif_dict = piexif.load(self.file)
            # Serialize metadata
            metadata_string = yaml.safe_dump(self.metadata)
            # Insert metadata into exif_dict
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = metadata_string.encode()
            # Convert new exif dict to exif bytes
            exif_bytes = piexif.dump(exif_dict)
            # Insert exif into file
            piexif.insert(exif_bytes, self.file)

    @property
    def metadata(self) -> dict:
        """
        Create basic metadata dictionary from basic capture data, 
        and any added custom metadata and tags.
        """
        d = {
            "id": self.id,
            "filename": self.filename,
            "time": self.timestring,
            "format": self.format,
            "tags": self.tags,
            "custom": self._metadata,
        }

        # Add custom metadata to dictionary
        return d

    @property
    def state(self) -> dict:
        """
        Return a dictionary of objects full state, including metadata.
        """

        # Create basic state dictionary
        d = {"path": self.file, "metadata": self.metadata}

        # Combined availability of data
        if self.exists:
            d["available"] = True
        else:
            d["available"] = False

        return d

    @property
    def data(self) -> io.BytesIO:
        """
        Return a byte string of the capture data.
        """

        if self.exists:  # If data file exists
            logging.info("Opening from file {}".format(self.file))
            with open(self.file, "rb") as f:
                d = io.BytesIO(f.read())  # Load bytes from file
            d.seek(0)  # Rewind loaded bytestream
            # Create a copy of the bytestream bytes
            data = io.BytesIO(d.getbuffer())
        else:
            data = None

        return data  # Read and return bytes data

    @property
    def binary(self) -> bytes:
        """Return a byte string of the capture data."""
        return self.data.getvalue()

    @property
    def thumbnail(self) -> io.BytesIO:
        """
        Returns a thumbnail of the capture data, for supported image formats.
        """
        global THUMBNAIL_SIZE
        # If no thumbnail exists, try and make one
        if not self.thumb_bytes:
            logging.info("Building thumbnail")
            self.thumb_bytes = io.BytesIO()
            if self.format.upper() in PIL_FORMATS:
                im = Image.open(self.data)
                im.thumbnail(THUMBNAIL_SIZE)
                im.save(self.thumb_bytes, self.format)
                self.thumb_bytes.seek(0)
        else:
            self.thumb_bytes.seek(0)

        # Copy the buffer, to avoid closing the file
        data = io.BytesIO(self.thumb_bytes.getbuffer())
        return data

    def save(self) -> None:
        """Write stream to file, and save/update metadata file"""
        # If a stream OR file exists, save the metadata file
        if self.exists:
            self.save_metadata()

    def delete(self) -> bool:
        """If the StreamObject has been saved, delete the file."""

        if os.path.isfile(self.file):
            logging.info("Deleting file {}".format(self.file))
            os.remove(self.file)

            return True
        else:
            return False

    def close(self):
        pass