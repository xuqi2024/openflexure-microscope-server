from fastapi.testclient import TestClient
from PIL import Image
import numpy as np
from pytest import fixture

from labthings_fastapi.server import ThingServer
from labthings_fastapi.client import ThingClient

from openflexure_microscope_server.things.camera.picamera import StreamingPiCamera2


@fixture(scope="module")
def client():
    """Initialise a test client for the StreamingPiCamera2 Thing.

    This fixture:

    * Sets up a ThingServer,
    * Registers a StreamingPiCamera2 instance at the "/camera/" endpoint
    * Provides a ThingClient for interacting with it during tests.
    """
    server = ThingServer()
    server.add_thing(StreamingPiCamera2(), "/camera/")
    with TestClient(server.app) as test_client:
        client = ThingClient.from_url("/camera/", client=test_client)
        yield client


def test_calibration(client):
    """Check that full auto calibrate completes without an exception."""
    client.full_auto_calibrate()


def test_jpeg_and_array(client):
    """Check that grabbing a jpeg from the stream results in the same size
    image as a array capture or a jpeg capture.
    """
    # Grab a jpeg from the stream
    blob = client.grab_jpeg()
    mjpeg_frame = Image.open(blob.open())
    assert mjpeg_frame

    # Capture a jpeg
    blob = client.capture_jpeg(resolution="main")
    jpeg_capture = Image.open(blob.open())
    assert jpeg_capture

    # Capture an array
    arrlist = client.capture_array(stream_name="main")
    array_main = np.array(arrlist)

    # Verify image sizes are the same
    assert mjpeg_frame.size == jpeg_capture.size
    assert array_main.shape[1::-1] == jpeg_capture.size
