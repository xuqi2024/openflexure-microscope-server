#!/usr/bin/env python
from api_client import APIconnection

import numpy as np
import unittest

import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO)


class TestCapture(unittest.TestCase):
    def test_capture_config(self):
        connection = APIconnection(host="localhost", port=5000, api_ver="v1")
        config = connection.get_config()

        expected_keys = ["image_resolution", "stream_resolution", "numpy_resolution"]

        for key in expected_keys:
            self.assertTrue(key in config)

    def test_capture_videoport(self):
        connection = APIconnection(host="localhost", port=5000, api_ver="v1")
        resolution = connection.get_config()["stream_resolution"]

        for resize in [None, (640, 480)]:

            if resize:
                resolution = resize

            capture_array = connection.capture(
                use_video_port=True,
                keep_on_disk=False,
                delete_after_use=True,
                resize=resize,
            )

            self.assertTrue(capture_array.shape == (resolution[1], resolution[0], 3))

    def test_capture_full(self):
        connection = APIconnection(host="localhost", port=5000, api_ver="v1")
        resolution = connection.get_config()["image_resolution"]

        for resize in [None, (640, 480)]:

            if resize:
                resolution = resize

            capture_array = connection.capture(
                use_video_port=False,
                keep_on_disk=False,
                delete_after_use=True,
                resize=resize,
            )

            self.assertTrue(capture_array.shape == (resolution[1], resolution[0], 3))


class TestStage(unittest.TestCase):
    def test_stage_config(self):
        connection = APIconnection(host="localhost", port=5000, api_ver="v1")
        config = connection.get_config()

        expected_keys = ["backlash"]

        for key in expected_keys:
            self.assertTrue(key in config)

    def test_stage_state(self):
        connection = APIconnection(host="localhost", port=5000, api_ver="v1")
        state = connection.get_state()

        self.assertTrue("stage" in state)

        expected_keys = ["position"]

        for key in expected_keys:
            self.assertTrue(key in state["stage"])

    def test_stage_movement(self):
        connection = APIconnection(host="localhost", port=5000, api_ver="v1")

        move_distance = 500
        for axis in range(3):
            for direction in [1, -1]:
                pos_i_dict = connection.get_state()["stage"]["position"]
                pos_i = [pos_i_dict["x"], pos_i_dict["y"], pos_i_dict["z"]]

                move = [0, 0, 0]
                move[axis] = move_distance * direction

                connection.move_by(*move)

                pos_f_dict = connection.get_state()["stage"]["position"]
                pos_f = [pos_f_dict["x"], pos_f_dict["y"], pos_f_dict["z"]]

                diff = np.subtract(pos_f, pos_i)
                logging.debug("{} > {}".format(pos_i, pos_f))

                self.assertTrue(np.array_equal(diff, move))


if __name__ == "__main__":

    suites = [
        unittest.TestLoader().loadTestsFromTestCase(TestCapture),
        unittest.TestLoader().loadTestsFromTestCase(TestStage),
    ]

    alltests = unittest.TestSuite(suites)

    result = unittest.TextTestRunner(verbosity=2).run(alltests)
