"""Check exposure times do not drift.

This can get very tedious. Recommend running pytest with -s option
to monitor progress.
"""

import logging
import time

from fastapi.testclient import TestClient

from labthings_fastapi.server import ThingServer
from labthings_fastapi.client import ThingClient

from openflexure_microscope_server.things.camera.picamera import StreamingPiCamera2

logging.basicConfig(level=logging.DEBUG)


def _test_exposure_time_drift(desired_time):
    """Capture 10 full resolution images and check that the exposure time remains constant.

    This confirms that automatic exposure time adjustment is fully turned off
    """
    cam = StreamingPiCamera2()
    server = ThingServer()
    server.add_thing(cam, "/camera/")

    with TestClient(server.app) as test_client:
        client = ThingClient.from_url("/camera/", client=test_client)
        exposure_tol = cam.persistent_control_tolerances["ExposureTime"]
        client.exposure_time = desired_time
        print(f"Setting desired time of {desired_time}")
        time.sleep(0.5)
        pre_capture_et = client.exposure_time
        print(f"Pre-capture the time is set to {pre_capture_et}")
        # Check exp is set correctly within known tolerance
        assert abs(pre_capture_et - desired_time) < exposure_tol

        for i in range(10):
            client.capture_jpeg(resolution="full")
            if i == 0:
                # Exposure can update on first capture, due to frame rate restrictions
                first_et = client.exposure_time
                assert abs(first_et - pre_capture_et) < exposure_tol
            else:
                frame_et = client.exposure_time
                print(f"Frame {i} captured with exposure time {frame_et}")
                # Check no further drift in value
                assert first_et == frame_et

        # Set the exposure time to the value it already is. To check it doesn't shift
        print(f"Setting exposure time to {frame_et} to check it doesn't change")
        client.exposure_time = frame_et
        time.sleep(0.5)
        # Check before and after capture
        assert client.exposure_time == frame_et
        client.capture_jpeg(resolution="full")
        assert client.exposure_time == frame_et
        print("Exposure time didn't change!!")
    print(f"End of test for exposure target {desired_time}")


def test_exposure_time_drift():
    """Performs the exposure time test for a range of exposure time values."""
    for desired_time in [100, 1000, 10000]:
        _test_exposure_time_drift(desired_time)
