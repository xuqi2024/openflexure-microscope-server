import io
import logging
from typing import Dict, Optional, Tuple

from flask import send_file
from labthings import Schema, fields, find_component
from labthings.views import ActionView

from openflexure_microscope.api.v2.views.captures import CaptureSchema


class CaptureResizeSchema(Schema):
    width = fields.Integer(metadata={"example": 640}, required=True)
    height = fields.Integer(metadata={"example": 480}, required=True)


class BasicCaptureArgs(Schema):
    use_video_port = fields.Boolean(load_default=False)
    bayer = fields.Boolean(
        load_default=False,
        metadata={"description": "Include raw bayer data in capture"},
    )
    resize = fields.Nested(CaptureResizeSchema(), required=False)


class FullCaptureArgs(BasicCaptureArgs):
    filename = fields.String(metadata={"example": "MyFileName"})
    temporary = fields.Boolean(
        load_default=False, metadata={"description": "Delete capture on shutdown"}
    )
    annotations = fields.Dict(
        load_default={}, metadata={"example": {"Client": "SwaggerUI"}}
    )
    tags = fields.List(fields.String, load_default=[], metadata={"example": ["docs"]})


class CaptureAPI(ActionView):
    """
    Create a new image capture. 
    """

    args = FullCaptureArgs()
    schema = CaptureSchema()

    def post(self, args):
        """
        Create a new capture
        """
        microscope = find_component("org.openflexure.microscope")

        resize_dict: Optional[Dict[str, int]] = args.get("resize", None)
        if resize_dict:
            resize: Optional[Tuple[int, int]] = (
                int(resize_dict["width"]),
                int(resize_dict["height"]),
            )  # Convert dict to tuple
        else:
            resize = None

        # Explicitally acquire lock (prevents empty files being created if lock is unavailable)
        with microscope.camera.lock:
            return microscope.capture(
                filename=args.get("filename"),
                temporary=args.get("temporary"),
                use_video_port=args.get("use_video_port"),
                resize=resize,
                bayer=args.get("bayer"),
                annotations=args.get("annotations"),
                tags=args.get("tags"),
            )


class RAMCaptureAPI(ActionView):
    """Take a non-persistent image capture."""

    args = BasicCaptureArgs()
    responses = {
        200: {
            "content": {"image/jpeg": {}},
            "description": "A JPEG image, representing the capture",
        }
    }

    def post(self, args):
        """
        Take a non-persistant image capture.
        """
        microscope = find_component("org.openflexure.microscope")

        resize_dict: Optional[Dict[str, int]] = args.get("resize", None)
        if resize_dict:
            resize: Optional[Tuple[int, int]] = (
                int(resize_dict["width"]),
                int(resize_dict["height"]),
            )  # Convert dict to tuple
        else:
            resize = None

        # Open a BytesIO stream to be destroyed once request has returned
        with microscope.camera.lock, io.BytesIO() as stream:

            microscope.camera.capture(
                stream,
                use_video_port=args.get("use_video_port"),
                resize=resize,
                bayer=args.get("bayer"),
            )

            stream.seek(0)

            return send_file(io.BytesIO(stream.getbuffer()), mimetype="image/jpeg")


class GPUPreviewStartAPI(ActionView):
    """
    Start the onboard GPU preview.
    Optional "window" parameter can be passed to control the position and size of the preview window,
    in the format ``[x, y, width, height]``.
    """

    args = {
        "window": fields.List(
            fields.Integer, load_default=[], metadata={"example": [0, 0, 640, 480]}
        )
    }

    def post(self, args):
        """
        Start the onboard GPU preview.
        """
        microscope = find_component("org.openflexure.microscope")

        # Get window argument from request
        window_arg = args.get("window")
        logging.debug(window_arg)

        # Default to no window
        fullscreen: bool = True
        window: Optional[Tuple[int, int, int, int]] = None

        # If request argument is well formed, use that
        if len(window_arg) == 4:
            fullscreen = False
            window = (int(w) for w in window_arg)

        microscope.camera.start_preview(fullscreen=fullscreen, window=window)
        return microscope.state


class GPUPreviewStopAPI(ActionView):
    def post(self):
        """
        Stop the onboard GPU preview.
        """
        microscope = find_component("org.openflexure.microscope")
        microscope.camera.stop_preview()
        return microscope.state
