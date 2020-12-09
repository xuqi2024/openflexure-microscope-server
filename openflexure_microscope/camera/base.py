# -*- coding: utf-8 -*-
import io
import logging
import time
from abc import ABCMeta, abstractmethod
from types import TracebackType
from typing import BinaryIO, List, NamedTuple, Optional, Tuple, Type, Union

from labthings import ClientEvent, StrictLock

JPEG_END_BYTES: bytes = b"\xff\xd9"

# Class to store a frames metadata
class TrackerFrame(NamedTuple):
    size: int
    time: float


class FrameStream(io.BytesIO):
    """
    A file-like object used to analyse and stream MJPEG frames.

    Instead of analysing a load of real MJPEG frames 
    after they've been stored in a BytesIO stream,
    we tell the camera to write frames to this class instead.

    We then do analysis as the frames are written, and discard 
    old frames as each new frame is written.
    """

    def __init__(self, *args, **kwargs):
        # Array of TrackerFrame objects
        io.BytesIO.__init__(self, *args, **kwargs)
        # Array of TrackerFramer objects
        self.frames: List[TrackerFrame] = []
        # Last acquired TrackerFramer object
        self.last: Optional[TrackerFrame] = None

        # Are we currently tracking frame sizes?
        self.tracking: bool = False

        # Event to track if a new frame is available since the last getvalue() call
        # We use a ClientEvent so that each thread can call getvalue() independantly
        self.new_frame: ClientEvent = ClientEvent()

        self._bad_frame: bool = False
        self.bad_frame_event: ClientEvent = ClientEvent()

    def __enter__(self):
        self.start_tracking()
        return super().__enter__()

    def __exit__(
        self,
        t: Optional[Type[BaseException]],
        value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        self.stop_tracking()
        return super().__exit__(t, value, traceback)

    def start_tracking(self):
        """Start tracking frame sizes"""
        if not self.tracking:
            logging.debug("Started tracking frame data")
            self.tracking = True

    def stop_tracking(self):
        """Stop tracking frame sizes"""
        if self.tracking:
            logging.debug("Stopped tracking frame data")
            self.tracking = False

    def reset_tracking(self):
        """Empty the array of tracked frame sizes"""
        self.frames = []

    def write(self, s):
        """
        Write a new frame to the FrameStream. Does a few things:
        1. If tracking frame size, store the size in self.frames
        2. Rewind and truncate the stream (delete previous frame)
        3. Store the new frame image
        4. Set the new_frame event
        """
        # If we get a bad frame, and the last frame was good
        if s[-2:] != JPEG_END_BYTES and not self._bad_frame:
            # TODO: Handle this more cleverly. Automatically lower bitrate to compensate?
            # Log error
            logging.error(
                "Incomplete frame data recieved. Camera bandwidth may have been exceeded. Consider lowing resolution, framerate, or target bitrate."
            )
            self.bad_frame_event.set()
            # Record that last frame was bad
            self._bad_frame = True
        # If the last frame was bad, but this frame was good
        elif self._bad_frame and s[-2:] == JPEG_END_BYTES:
            # Clear the bad frame record
            self._bad_frame = False
            # self.bad_frame_event.clear()
        # If we're tracking frame size
        if self.tracking:
            frame = TrackerFrame(size=len(s), time=time.time())
            self.frames.append(frame)
            self.last = frame
        # Reset the stream for the next frame
        super().seek(0)
        super().truncate()
        # Write the new frame
        super().write(s)
        # Set the new frame event
        self.new_frame.set()

    def getvalue(self) -> bytes:
        """Clear tne new_frame event and return frame data"""
        self.new_frame.clear()
        return super().getvalue()

    def getframe(self) -> bytes:
        """Wait for a new frame to be available, then return it"""
        self.new_frame.wait()
        return self.getvalue()


class BaseCamera(metaclass=ABCMeta):
    """
    Base implementation of StreamingCamera.
    """

    def __init__(self):
        #: :py:class:`labthings.StrictLock`: Access lock for the camera
        self.lock: StrictLock = StrictLock(name="Camera", timeout=None)
        #: :py:class:`FrameStream`: Streaming and analysis frame buffer
        self.stream: FrameStream = FrameStream()

        self.stream_active: bool = False
        self.record_active: bool = False
        self.preview_active: bool = False

        self.image_resolution: Tuple[int, int] = (1312, 976)
        self.stream_resolution: Tuple[int, int] = (640, 480)

    @property
    @abstractmethod
    def configuration(self):
        """The current camera configuration."""

    @property
    @abstractmethod
    def state(self):
        """The current read-only camera state."""

    @property
    def settings(self):
        return self.read_settings()

    @abstractmethod
    def start_stream(self):
        """Ensure the frame stream is actively running"""

    @abstractmethod
    def stop_stream(self):
        """Stop the active stream, if possible"""

    @abstractmethod
    def update_settings(self, config: dict):
        """Update settings from a config dictionary"""

    @abstractmethod
    def read_settings(self) -> dict:
        """Return the current settings as a dictionary"""

    @abstractmethod
    def capture(
        self,
        output: Union[str, BinaryIO],
        fmt: str = "jpeg",
        use_video_port: bool = False,
        resize: Optional[Tuple[int, int]] = None,
        bayer: bool = True,
        thumbnail: Optional[Tuple[int, int, int]] = None,
    ):
        """
        Perform a basic capture to output
        
        Args:
            output: String or file-like object to write capture data to
            fmt: Format of the capture.
            use_video_port: Capture from the video port used for streaming. Lower resolution, faster.
            resize: Resize the captured image.
            bayer: Store raw bayer data in capture
            thumbnail: Dimensions and quality (x, y, quality) of a thumbnail to generate, if supported
        """

    def start_worker(self, **_) -> bool:
        """Start the background camera thread if it isn't running yet."""
        logging.warning(
            "`start_worker` method has been deprecated and is no longer required. Please avoid calling this method."
        )
        return True

    def get_frame(self) -> bytes:
        """
        Return the current camera frame.

        Just an alias of self.stream.getframe()
        """
        return self.stream.getframe()

    def __enter__(self):
        """Create camera on context enter."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close camera stream on context exit."""
        self.close()

    def close(self):
        """Close the BaseCamera and all attached StreamObjects."""
        logging.info("Closed %s", (self))
