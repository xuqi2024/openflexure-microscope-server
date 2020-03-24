from openflexure_microscope.api.utilities import get_bool, JsonResponse
from labthings.server.view import View
from labthings.server.find import find_component
from labthings.server.decorators import (
    use_args,
    marshal_with,
    doc,
    tag,
    ThingAction,
    doc_response,
)

from labthings.server import fields
from openflexure_microscope.utilities import filter_dict

from openflexure_microscope.api.v2.views.captures import capture_schema

import logging
import io
from flask import jsonify, request, abort, url_for, redirect, send_file


@ThingAction
class CaptureAPI(View):
    """
    Create a new image capture. 
    """

    @use_args(
        {
            "filename": fields.String(example="MyFileName"),
            "temporary": fields.Boolean(
                missing=False, description="Delete capture on shutdown"
            ),
            "use_video_port": fields.Boolean(missing=False),
            "bayer": fields.Boolean(
                missing=False, description="Store raw bayer data in file"
            ),
            "annotations": fields.Dict(missing={}, example={"Client": "SwaggerUI"}),
            "tags": fields.List(fields.String, missing=[], example=["docs"]),
            "resize": fields.Dict(
                missing=None, example={"width": 640, "height": 480}
            ),  # TODO: Validate keys
        }
    )
    @marshal_with(capture_schema)
    @doc_response(200, description="Capture successful")
    def post(self, args):
        """
        Create a new capture
        """
        microscope = find_component("org.openflexure.microscope")

        resize = args.get("resize", None)
        if resize:
            if ("width" in resize) and ("height" in resize):
                resize = (
                    int(resize["width"]),
                    int(resize["height"]),
                )  # Convert dict to tuple
            else:
                abort(404)

        # Explicitally acquire lock (prevents empty files being created if lock is unavailable)
        with microscope.camera.lock:
            output = microscope.camera.new_image(
                temporary=args.get("temporary"), filename=args.get("filename")
            )

            microscope.camera.capture(
                output.file,
                use_video_port=args.get("use_video_port"),
                resize=resize,
                bayer=args.get("bayer"),
            )

            # Inject system metadata
            output.put_metadata({"instrument": microscope.metadata})

            # Insert custom metadata
            output.put_annotations(args.get("annotations"))
            # Insert custom tags
            output.put_tags(args.get("tags"))

        return output


@ThingAction
class RAMCaptureAPI(View):
    """
    Take a non-persistant image capture.
    """

    @use_args(
        {
            "use_video_port": fields.Boolean(missing=True),
            "bayer": fields.Boolean(
                missing=False, description="Return with raw bayer data"
            ),
            "resize": fields.Dict(
                missing=None, example={"width": 640, "height": 480}
            ),  # TODO: Validate keys
        }
    )
    @doc_response(200, mimetype="image/jpeg")
    def post(self, args):
        """
        Take a non-persistant image capture.
        """
        microscope = find_component("org.openflexure.microscope")

        resize = args.get("resize", None)
        if resize:
            if ("width" in resize) and ("height" in resize):
                resize = (
                    int(resize["width"]),
                    int(resize["height"]),
                )  # Convert dict to tuple
            else:
                abort(404)

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


@ThingAction
class GPUPreviewStartAPI(View):
    """
    Start the onboard GPU preview.
    Optional "window" parameter can be passed to control the position and size of the preview window,
    in the format ``[x, y, width, height]``.
    """

    @use_args(
        {"window": fields.List(fields.Integer, missing=[], example=[0, 0, 640, 480])}
    )
    def post(self, args):
        """
        Start the onboard GPU preview.
        """
        microscope = find_component("org.openflexure.microscope")

        window = args.get("window")
        logging.debug(window)

        if len(window) != 4:
            fullscreen = True
            window = None
        else:
            fullscreen = False
            window = [int(w) for w in window]

        microscope.camera.start_preview(fullscreen=fullscreen, window=window)

        # TODO: Make schema for microscope state
        return jsonify(microscope.state)


@ThingAction
class GPUPreviewStopAPI(View):
    def post(self):
        """
        Stop the onboard GPU preview.
        """
        microscope = find_component("org.openflexure.microscope")
        microscope.camera.stop_preview()
        # TODO: Make schema for microscope state
        return jsonify(microscope.state)
