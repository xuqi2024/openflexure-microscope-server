"""Test changing and setting camerat modes on the Raspberry Picamera."""

import logging

from fastapi.testclient import TestClient
import numpy as np

from labthings_fastapi.server import ThingServer
from labthings_fastapi.client import ThingClient

from openflexure_microscope_server.things.camera.picamera import StreamingPiCamera2

logging.basicConfig(level=logging.DEBUG)


def test_sensor_mode():
    """Test capturing raw arrays in two different sensor modes."""
    cam = StreamingPiCamera2()
    server = ThingServer()
    server.add_thing(cam, "/camera/")

    with TestClient(server.app) as test_client:
        client = ThingClient.from_url("/camera/", client=test_client)
        for size in [(3280, 2464), (1640, 1232)]:
            client.sensor_mode = {"output_size": size, "bit_depth": 10}
            arr = np.array(client.capture_array(stream_name="raw"))
            # Check that the array dimensions match the requested image size.
            # Note: Numpy array shape is (y,x), but the sensor is set with (x,y)
            # hence the need to compare index 0 with index 1.
            assert arr.shape[0] == size[1]
