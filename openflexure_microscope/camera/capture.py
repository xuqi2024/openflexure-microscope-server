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

"""
Attributes:
    BASE_CAPTURE_PATH (str): Base path to store all captures
    TEMP_CAPTURE_PATH (str): Base path to store all temporary captures (automatically emptied)
"""

PIL_FORMATS = ['JPG', 'JPEG', 'PNG', 'TIF', 'TIFF']
EXIF_FORMATS = ['JPG', 'JPEG', 'TIF', 'TIFF']
THUMBNAIL_SIZE = (200, 150)

BASE_CAPTURE_PATH = os.path.join(os.path.expanduser('~'), 'micrographs')
TEMP_CAPTURE_PATH = os.path.join(BASE_CAPTURE_PATH, 'tmp')


# TODO: Move these methods to a camera utilities module?
def clear_tmp():
    """
    Removes all files in the ``TEMP_CAPTURE_PATH`` directory
    """
    global TEMP_CAPTURE_PATH

    if os.path.isdir(TEMP_CAPTURE_PATH):
        logging.info("Clearing {}...".format(TEMP_CAPTURE_PATH))
        shutil.rmtree(TEMP_CAPTURE_PATH)
        logging.debug("Cleared {}.".format(TEMP_CAPTURE_PATH))


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
    if 'Exif' in exif_dict and 37510 in exif_dict['Exif']:
        return yaml.load(exif_dict['Exif'][37510].decode())
    else:
        return None


def make_file_list(directory, formats):
    files = []
    for fmt in formats:
        files.extend(glob.glob('{}/**/*.{}'.format(directory, fmt.lower()), recursive=True))

    logging.info("{} capture files found on disk".format(len(files)))

    return files


def build_captures_from_exif():
    global BASE_CAPTURE_PATH, EXIF_FORMATS

    logging.debug("Reloading captures from {}...".format(BASE_CAPTURE_PATH))
    files = make_file_list(BASE_CAPTURE_PATH, EXIF_FORMATS)
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
    capture = CaptureObject(
        filepath=path
    ) 

    # Build file path information
    capture.split_file_path(capture.file)

    # Populate capture parameters
    capture.id = exif_dict['id']
    
    capture.timestring = exif_dict['time']
    capture.format = exif_dict['format']

    capture._metadata = exif_dict['custom']
    capture.tags = exif_dict['tags']

    return capture


class CaptureObject(object):
    """
    StreamObject used to store and process capture data, and metadata.

    Attributes:
        timestring (str): Timestring of capture creation time
        temporary (bool): Mark the capture as temporary, to be deleted as the server closes,
            or as resources are required
        _metadata (dict): Dictionary of custom metadata to be included in metadata file
        tags (list): List of tags. Essentially just as extra custom metadata field, but useful for quick organisation
        bytestream (:py:class:`io.BytesIO`): Byte bytestream that data will be written to
        filefolder (str): Folder in which the capture file will be stored
        filename (str): Full name of the capture file
        basename (str): Filename of the capture, without a file extension
        format (str): Format of the capture data

    Notes:
        Captures cannot be stored in a lower-level directory than BASE_CAPTURE_PATH.
    """

    def __init__(
            self,
            write_to_file: bool = False,
            temporary: bool = False,
            filepath: str = '') -> None:
        """Create a new StreamObject, to manage capture data."""

        # Store a nice ID
        self.id = uuid.uuid4().hex  #: str: Unique capture ID
        logging.debug("Created StreamObject {}".format(self.id))
        self.timestring = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Keep on disk after close by default
        self.temporary = temporary

        # Create file name. Default to UUID
        if not filepath:
            self.file = self.build_file_path()
        else:
            self.file = filepath
        self.split_file_path(self.file)

        # Dictionary for storing custom metadata
        self._metadata = {}

        # List for storing tags
        self.tags = []

        # Byte bytestream properties
        self.bytestream = io.BytesIO()

        # Set default write target
        if not write_to_file:
            self.stream = self.bytestream
        else:
            self.stream = self.file

        # Log if created by context manager
        self.context_manager = False

        # Thumbnail (populated only for PIL captures)
        self.thumb_bytes = None

    def __enter__(self):
        """Create StreamObject in context, to auto-clean disk data."""
        logging.debug(
            "Entering context for {}. Stored files will be cleaned up automatically regardless of location.".format(
                self.id))
        self.temporary = True  # Flag file to be removed on close.
        self.context_manager = True  # Used in metadata

        logging.info("Rebuilding as a temporary capture...")
        self.build_file_path()

        return self

    def __exit__(self, *args):
        """Exit StreamObject, and auto-clean disk data."""
        logging.info("Cleaning up {}".format(self.id))
        self.close()

    def build_file_path(self):
        """
        Construct a full file path, based on filename, folder, and file format.
        Defaults to UUID.
        """
        global TEMP_CAPTURE_PATH, BASE_CAPTURE_PATH 
        if self.temporary:
            base_dir = TEMP_CAPTURE_PATH
        else:
            base_dir = BASE_CAPTURE_PATH
        return os.path.join(base_dir, self.filename)  # Full file name by joining given folder to given name

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
        self.format = self.filename.split('.')[-1]

        # Create folder and file
        if not os.path.exists(self.filefolder):
            os.makedirs(self.filefolder)

    @property
    def stream_exists(self, auto_rewind=True) -> bool:
        """Check if capture data BytesIO bytestream exists in memory."""
        if auto_rewind:
            self.bytestream.seek(0)  # Rewind the data bytes for reading
        if self.bytestream.getvalue():  # If data bytestream contains data
            self.bytestream.seek(0)  # Rewind the data bytes for reading
            return True
        else:
            self.bytestream.seek(0)  # Rewind the data bytes for reading
            return False

    @property
    def file_exists(self) -> bool:
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

        if self.format.upper() in EXIF_FORMATS and self.file_exists:
            logging.debug("Writing exif data to capture file")
            # Extract current Exif data
            exif_dict = piexif.load(self.file)
            # Serialize metadata
            metadata_string = yaml.safe_dump(self.metadata)
            # Insert metadata into exif_dict
            exif_dict['Exif'][piexif.ExifIFD.UserComment] = metadata_string.encode()
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
        d = {'id': self.id, 'filename': self.filename, 'time': self.timestring,
             'format': self.format, 'tags': self.tags, 'custom': self._metadata}

        # Add custom metadata to dictionary
        return d

    @property
    def yaml(self) -> str:
        """
        Return a string containing a YAML-formatted representation of the capture matadata
        """
        return yaml.dump(self.metadata, default_flow_style=False)

    @property
    def exists(self) -> bool:
        """
        Check if either an in-memory byte stream or on-disk file of capture data exists.

        If False, the capture data cannot be obtained.
        """
        return self.stream_exists or self.file_exists

    @property
    def state(self) -> dict:
        """
        Return a dictionary of objects full state, including metadata.
        """

        # Create basic state dictionary
        d = {'path': self.file, 'temporary': self.temporary, 'metadata': self.metadata}

        # Check bytestream
        if self.stream_exists:
            d['bytestream'] = True
        else:
            d['bytestream'] = False

        # Combined availability of data
        if self.exists:
            d['available'] = True
        else:
            d['available'] = False

        return d

    @property
    def data(self) -> io.BytesIO:
        """
        Return a byte string of the capture data.
        
        If the capture data exists in-memory, this will be loaded. If the data only exists
        on disk, this will automatically fall back to loading from disk.
        """
        self.bytestream.seek(0)  # Rewind the data bytes for reading

        if self.stream_exists:  # If data bytestream contains data
            # Create a copy of the bytestream bytes
            logging.debug("STREAM EXISTS")
            data = io.BytesIO(self.bytestream.getbuffer())

        else:  # If data bytestream is empty
            if self.file_exists:  # If data file exists
                logging.info("Opening from file {}".format(self.file))
                with open(self.file, 'rb') as f:
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

    def load_file(self) -> bool:
        """Load data stored on disk to the in-memory bytestream."""
        if self.file_exists:  # If data file exists
            with open(self.file, 'rb') as f:
                self.bytestream = io.BytesIO(f.read())  # Load bytes from file
            self.bytestream.seek(0)  # Rewind data bytes again
            return True
        else:
            return False

    def save_file(self) -> bool:
        """Write the StreamObjects bytestream to a file."""
        if self.stream_exists:  # If there's a bytestream to save
            with open(self.file, 'ab') as f:  # Load file as bytes
                logging.debug("Writing bytestream to file {}".format(self.file))
                f.seek(0, 0)  # Seek to the start of the file
                f.write(self.binary)  # Write data bytes to file
            return True
        else:
            return False

    def save(self) -> None:
        """Write stream to file, and save/update metadata file"""
        # Try to save the file (only succeeds if an unsaved stream exists)
        self.save_file()

        # If a stream OR file exists, save the metadata file
        if self.exists:
            self.save_metadata()

    def delete_stream(self):
        """Clear the BytesIO bytestream of the StreamObject."""
        self.bytestream = io.BytesIO()

    def delete_file(self) -> bool:
        """If the StreamObject has been saved, delete the file."""

        if os.path.isfile(self.file):
            logging.info("Deleting file {}".format(self.file))
            os.remove(self.file)

            return True
        else:
            return False

    def delete(self):
        """Entirely delete all capture data."""
        logging.info("Deleting {}".format(self.id))
        self.delete_stream()
        self.delete_file()

    def shunt(self):
        """Demote the StreamObject from being stored in memory."""
        if not self.file_exists:  # If file doesn't already exist
            self.save()  # Save bytestream to disk, if it exists
        self.delete_stream()  # Delete the bytestream from memory

    def close(self):
        """Both clear the bytestream, and delete any associated on-disk data."""
        logging.info("Closing {}".format(self.id))
        self.delete_stream()
        # Delete the file from disk if temporary
        if self.temporary:
            self.delete()


atexit.register(clear_tmp)
