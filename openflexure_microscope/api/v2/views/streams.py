from flask import Response
from labthings import find_component
from labthings.views import PropertyView
from datetime import datetime


def gen(camera):
    """Video streaming generator function."""
    while True:
        # the obtained frame is a jpeg
        frame: bytes = camera.stream.getframe()

        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


def format_sse(event: str, data: str) -> str:
    msg = f"data: {datetime.now().isoformat()}: {data}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    return msg


class MjpegStream(PropertyView):
    """
    Real-time MJPEG stream from the microscope camera
    """

    responses = {200: {"content_type": "multipart/x-mixed-replace"}}

    def get(self):
        """
        MJPEG stream from the microscope camera.

        Note: While the code actually getting frame data from a camera and storing it in
        camera.frame runs in a thread, the gen(microscope.camera) generator does not.
        This response is therefore blocking. The generator just yields the most recent
        frame from the camera object, passed to the Flask response, and then repeats until
        the connection is closed.

        Without monkey patching, or using a native threaded server, the stream
        will block all proceeding requests.
        """
        microscope = find_component("org.openflexure.microscope")

        return Response(
            gen(microscope.camera), mimetype="multipart/x-mixed-replace; boundary=frame"
        )


class SnapshotStream(PropertyView):
    """
    Single JPEG snapshot from the camera stream
    """

    responses = {200: {"content_type": "image/jpeg", "description": "Snapshot taken"}}

    def get(self):
        """
        Single snapshot from the camera stream
        """
        microscope = find_component("org.openflexure.microscope")

        return Response(microscope.camera.stream.getframe(), mimetype="image/jpeg")


class MjpegFrameState(PropertyView):
    """
    Real-time MJPEG stream from the microscope camera
    """

    responses = {200: {"content_type": "text/event-stream"}}

    def get(self):
        microscope = find_component("org.openflexure.microscope")

        def stream():
            while True:
                microscope.camera.stream.bad_frame_event.wait()
                msg = format_sse(
                    "bitrateLimitExceeded",
                    "Incomplete frame data recieved. Camera bandwidth may have been exceeded. Consider lowing resolution, framerate, or target bitrate.",
                )
                microscope.camera.stream.bad_frame_event.clear()

                yield msg

        return Response(stream(), mimetype="text/event-stream")

