"""Test the server without creating a full HTTP server and socket connection.

Rather than spinning up a full uvicorn webserver for each test these tests use
the FastAPI ``TestClient`` or to directly communicate with the underlying
LabThings-FastAPI code. This increases speed of testing significantly.

For tests that require a full running server see the ``integration-tests``
directory in the root of the repository.
"""

import json
import os
import tempfile

from fastapi.testclient import TestClient
from PIL import Image
import numpy as np
import piexif
import pytest

import labthings_fastapi as lt

from openflexure_microscope_server.things.camera.simulation import SimulatedCamera
from openflexure_microscope_server.things.stage.dummy import DummyStage
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper
from openflexure_microscope_server.things import camera_stage_mapping

camera_stage_mapping.DEFAULT_SETTLING_TIME = 0  # skip the settling time for tests


@pytest.fixture
def thing_server():
    """Yield a server with a very basic configuration."""
    temp_folder = tempfile.TemporaryDirectory()
    server = lt.ThingServer(settings_folder=temp_folder.name)
    server.add_thing(
        SimulatedCamera(
            shape=(240, 320, 3), canvas_shape=(960, 1240, 3), frame_interval=0.01
        ),
        "/camera/",
    )
    server.add_thing(DummyStage(step_time=0.000001), "/stage/")
    server.add_thing(AutofocusThing(), "/autofocus/")
    server.add_thing(CameraStageMapper(), "/camera_stage_mapping/")
    assert os.path.exists(os.path.join(temp_folder.name, "camera/"))
    # Note: yield is important. If return is used the temp folder gets deleted
    # before the test runs
    yield server


@pytest.fixture
def client(thing_server):
    """Yield a FastAPI TestClient for the server."""
    with TestClient(thing_server.app) as client:
        yield client


@pytest.fixture
def slower_client(thing_server):
    """Yield a FastAPI TestClient for the server with a slower moving stage.

    The step time for the stage is 100 microseconds rather than
    1 microsecond.
    """
    thing_server.things["/stage/"].step_time = 0.0001
    with TestClient(thing_server.app) as client:
        yield client


def test_autofocus(slower_client):
    """Test Fast Autofocus can run doesn't raise an exception."""
    client = slower_client
    autofocus = lt.ThingClient.from_url("/autofocus/", client)
    _ = autofocus.fast_autofocus()


def test_grab_jpeg(client):
    """Check that grab_jpeg returns a blob that can be opened."""
    camera = lt.ThingClient.from_url("/camera/", client)
    blob = camera.grab_jpeg()
    _image = Image.open(blob.open())


def test_capture_jpeg_metadata(client):
    """Check that the position is encoded into the image metadata."""
    camera = lt.ThingClient.from_url("/camera/", client)
    blob = camera.capture_jpeg()
    image = Image.open(blob.open())
    exif_dict = piexif.load(image.info["exif"])
    encoded_metadata = exif_dict["Exif"][piexif.ExifIFD.UserComment]
    metadata = json.loads(encoded_metadata)
    assert "position" in metadata["/stage/"]


def test_stage(client):
    """Test moving th stage forwards and backwards."""
    stage = lt.ThingClient.from_url("/stage/", client)
    start = stage.position
    move = {"x": 1, "y": 2, "z": 3}
    stage.move_relative(**move)
    pos = stage.position
    for s, m, p in zip(start.values(), move.values(), pos.values()):
        assert s + m == p
    stage.move_relative(**{k: -v for k, v in move.items()})
    pos = stage.position
    for s, p in zip(start.values(), pos.values()):
        assert s == p


def test_capture_array(client):
    """Capture array from simulation and check the size is as expected."""
    camera = lt.ThingClient.from_url("/camera/", client)
    array = np.asarray(camera.capture_array())
    assert array.shape == (240, 320, 3)


def test_camera_stage_mapping_calibration(client):
    """Check that camera stage mapping can run without an exception."""
    camera_stage_mapping = lt.ThingClient.from_url("/camera_stage_mapping/", client)
    camera_stage_mapping.calibrate_xy()
