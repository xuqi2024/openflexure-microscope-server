import json
import os
import tempfile

from fastapi.testclient import TestClient
from labthings_fastapi.client import ThingClient
from PIL import Image
import numpy as np
import piexif
import pytest

from openflexure_microscope_server.server import ThingServer
from openflexure_microscope_server.things.camera.simulation import SimulatedCamera
from openflexure_microscope_server.things.stage.dummy import DummyStage
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper
from openflexure_microscope_server.things.smart_scan import (
    SmartScanThing,
    BackgroundDetectThing,
)
from openflexure_microscope_server.things.settings_manager import SettingsManager
from openflexure_microscope_server.things.auto_recentre_stage import RecentringThing
from openflexure_microscope_server.things import camera_stage_mapping

camera_stage_mapping.DEFAULT_SETTLING_TIME = 0  # skip the settling time for tests


@pytest.fixture
def thing_server():
    temp_folder = tempfile.TemporaryDirectory()
    server = ThingServer(settings_folder=temp_folder.name)
    server.add_thing(
        SimulatedCamera(
            shape=(240, 320, 3), canvas_shape=(960, 1240, 3), frame_interval=0.01
        ),
        "/camera/",
    )
    server.add_thing(DummyStage(step_time=0.000001), "/stage/")
    server.add_thing(AutofocusThing(), "/autofocus/")
    server.add_thing(CameraStageMapper(), "/camera_stage_mapping/")
    server.add_thing(
        SmartScanThing(
            path_to_openflexure_stitch=r".\.venv_stitching\Scripts\openflexure-stitch.exe"
        ),
        "/smart_scan/",
    )
    server.add_thing(BackgroundDetectThing(), "/background_detect/")
    server.add_thing(SettingsManager(), "/settings/")
    server.add_thing(RecentringThing(), "/auto_recentre_stage/")
    assert os.path.exists(os.path.join(temp_folder.name, "camera/"))
    # NB yield is important: otherwise, the temp folder gets deleted before the test runs
    yield server


@pytest.fixture
def client(thing_server):
    with TestClient(thing_server.app) as client:
        csm = thing_server.things["/camera_stage_mapping/"]
        csm.thing_settings["image_to_stage_displacement_matrix"] = [
            [10, 0],
            [0, 10],
        ]
        yield client


@pytest.fixture
def slower_client(thing_server):
    thing_server.things["/stage/"].step_time = 0.0001
    with TestClient(thing_server.app) as client:
        yield client


def test_autofocus(slower_client):
    client = slower_client
    autofocus = ThingClient.from_url("/autofocus/", client)
    _ = autofocus.fast_autofocus()


def test_grab_jpeg(client):
    camera = ThingClient.from_url("/camera/", client)
    blob = camera.grab_jpeg()
    _image = Image.open(blob.open())


def test_capture_jpeg_metadata(client):
    camera = ThingClient.from_url("/camera/", client)
    blob = camera.capture_jpeg()
    image = Image.open(blob.open())
    exif_dict = piexif.load(image.info["exif"])
    encoded_metadata = exif_dict["Exif"][piexif.ExifIFD.UserComment]
    metadata = json.loads(encoded_metadata)
    assert "position" in metadata["/stage/"]


def test_stage(client):
    stage = ThingClient.from_url("/stage/", client)
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
    camera = ThingClient.from_url("/camera/", client)
    array = np.asarray(camera.capture_array())
    assert array.shape == (240, 320, 3)


def test_camera_stage_mapping_calibration(client):
    camera_stage_mapping = ThingClient.from_url("/camera_stage_mapping/", client)
    camera_stage_mapping.calibrate_xy()
    matrix = camera_stage_mapping.image_to_stage_displacement_matrix
    for line in matrix:
        assert len(line) == 2


def test_sample_scan(client):
    scanner = ThingClient.from_url("/smart_scan/", client)
    scanner.sample_scan()
