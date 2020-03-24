#!/usr/bin/env python
from openflexure_stage import OpenFlexureStage

import numpy as np

import unittest

import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO)


class TestMicroscope(unittest.TestCase):
    def test_movement(self):
        move_distance = 500
        for axis in range(3):
            for direction in [1, -1]:
                pos_i = stage.position
                logging.debug(pos_i)

                logging.info(
                    "Moving axis {} by {}".format(axis, move_distance * direction)
                )
                move = [0, 0, 0]
                move[axis] = move_distance * direction

                stage.move_rel(move)

                pos_f = stage.position
                diff = np.subtract(pos_f, pos_i)
                logging.debug("{} > {}".format(pos_i, pos_f))

                self.assertTrue(np.array_equal(diff, move))


if __name__ == "__main__":
    with OpenFlexureStage("/dev/ttyUSB0") as stage:

        suites = [unittest.TestLoader().loadTestsFromTestCase(TestMicroscope)]

        alltests = unittest.TestSuite(suites)

        result = unittest.TextTestRunner(verbosity=2).run(alltests)
