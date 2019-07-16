#!/usr/bin/env python
from openflexure_microscope.camera.pi import PiCameraStreamer, CaptureObject

import os
import io
import time
import numpy as np

from PIL import Image

import unittest

import logging
import sys
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


class TestCaptureMethods(unittest.TestCase):

    def test_still_capture(self):
        """Tests capturing still images to a BytesIO stream."""
        global camera

        for use_video_port in [True, False]:
            for resize in [None, (640, 480)]:

                # Wait for camera
                camera.wait_for_camera()

                # Capture to a context (auto-deletes files when done)
                with camera.new_image(write_to_file=False) as output:

                    camera.capture(
                        output, 
                        use_video_port=use_video_port, 
                        resize=resize
                    ) 

                    # Ensure file deletion fails and returns False
                    self.assertFalse(output.delete_file())
                    # Ensure capture not stored to file
                    self.assertFalse(os.path.isfile(output.file))

                    # BEFORE DELETE: Ensure StreamObject 'stream' has
                    # a valid BytesIO object and byte string
                    self.assertTrue(isinstance(
                        output.data,
                        io.IOBase
                        ))
                    self.assertTrue(isinstance(
                        output.binary,
                        (bytes, bytearray)
                        ))

                    # Save capture to file
                    output.save_file()
                    # Check file got saved
                    self.assertTrue(os.path.isfile(output.file))

                    # Delete file
                    output.delete_file()
                    # Check file got deleted
                    self.assertFalse(os.path.isfile(output.file))

                    # AFTER DELETE: Ensure StreamObject 'stream' has
                    # a valid BytesIO object and byte string
                    self.assertTrue(isinstance(output.data, io.IOBase))
                    self.assertTrue(isinstance(
                        output.binary,
                        (bytes, bytearray)
                        ))

                    # Create a PIL image from stream
                    image = Image.open(output.data)

                    # Ensure a valid PIL image was created
                    self.assertTrue(isinstance(image, Image.Image))

                    # Calculate expected dimensions
                    if resize:
                        dims = resize
                    else:
                        if use_video_port:
                            dims = camera.stream_resolution
                        else:
                            dims = camera.image_resolution

                    # Ensure PIL image size matches expected size
                    print(image.size, dims)
                    self.assertTrue(image.size == dims)

    def test_still_store(self):
        """Tests capturing still images to a file on disk."""
        global camera

        for use_video_port in [True, False]:
            for resize in [None, (640, 480)]:
                # Wait for camera
                camera.wait_for_camera()

                # Capture
                output = camera.capture(
                    camera.new_image(write_to_file=True),
                    use_video_port=use_video_port,
                    resize=resize)

                # Check file got saved
                self.assertTrue(os.path.isfile(output.file))
                statinfo = os.stat(output.file)
                self.assertTrue(statinfo.st_size > 0)

                # Ensure StreamObject 'stream' has
                # a valid BytesIO object and byte string
                self.assertTrue(isinstance(output.data, io.IOBase))
                self.assertTrue(isinstance(output.binary, (bytes, bytearray)))

                # Ensure file deletion completes and returns True
                self.assertTrue(output.delete_file())

                # Check file got deleted
                self.assertFalse(os.path.isfile(output.file))


class TestUnencodedMethods(unittest.TestCase):

    def test_yuv_array(self):
        """Tests capturing unencoded YUV data to a Numpy array."""
        global camera

        for use_video_port in [True, False]:
            for resize in [None, (640, 480)]:

                print("{}, {}, {}".format(id, resize, use_video_port))

                # Wait for camera
                camera.wait_for_camera()

                # Capture RGB array
                yuv = camera.yuv(
                    use_video_port=use_video_port,
                    resize=resize)

                # Ensure capture output is a valid numpy array
                self.assertTrue(isinstance(yuv, np.ndarray))

                # Calculate expected dimensions
                if resize:
                    dims = resize
                else:
                    if use_video_port:
                        dims = camera.stream_resolution
                    else:
                        dims = camera.numpy_resolution

                # Ensure array shape matches expected dimensions
                self.assertTrue(yuv.shape == (dims[1], dims[0], 3))

    def test_rgb_array(self):
        """Tests capturing unencoded YUV/RGB data to a Numpy array."""
        global camera

        for use_video_port in [True, False]:
            for resize in [None, (640, 480)]:

                print("{}, {}, {}".format(id, resize, use_video_port))

                # Wait for camera
                camera.wait_for_camera()

                # Capture RGB array
                rgb = camera.array(
                    use_video_port=use_video_port,
                    resize=resize)

                # Ensure capture output is a valid numpy array
                self.assertTrue(isinstance(rgb, np.ndarray))

                # Calculate expected dimensions
                if resize:
                    dims = resize
                else:
                    if use_video_port:
                        dims = camera.stream_resolution
                    else:
                        dims = camera.numpy_resolution

                # Ensure array shape matches expected dimensions
                self.assertTrue(rgb.shape == (dims[1], dims[0], 3))


class TestRecordMethods(unittest.TestCase):

    def test_video_record(self):
        """Tests recording videos to BytesIO stream, and to file on disk."""
        global camera

        for write_to_file in [True, False, None]:

            logging.debug("\nWRITE TO FILE: {}".format(write_to_file))

            # Wait for camera
            camera.wait_for_camera()

            with camera.new_video(
                write_to_file=write_to_file
            ) as output:

                # Start recording
                camera.start_recording(output)

                # Record for 2 seconds
                time.sleep(2)
                # Stop recording
                camera.stop_recording()

                # Check stream
                self.assertTrue(isinstance(output.data, io.IOBase))
                self.assertTrue(isinstance(output.binary, (bytes, bytearray)))

                # Check file
                if write_to_file:
                    statinfo = os.stat(output.file)
                    self.assertTrue(statinfo.st_size > 0)

                # Log path
                temp_path = output.file

            # Check file got deleted on __exit__
            self.assertFalse(os.path.isfile(temp_path))

            time.sleep(0.25)

    def test_video_store(self):
        """Tests recording videos to file on disk, without context manager."""
        global camera

        # Wait for camera
        camera.wait_for_camera()

        # Start recording
        output = camera.start_recording(camera.new_video())

        # Record for 2 seconds
        time.sleep(2)
        # Stop recording
        camera.stop_recording()

        # Check file
        statinfo = os.stat(output.file)
        self.assertTrue(statinfo.st_size > 0)

        # Ensure file deletion completes and returns True
        self.assertTrue(output.delete_file())

        # Check file got deleted
        self.assertFalse(os.path.isfile(output.file))


class TestThreadStarting(unittest.TestCase):
    def test_restarting_stream(self):
        """Tests that a capture call restarts the camera worker thread."""
        global camera

        # Wait for camera
        camera.wait_for_camera()

        # Force-stop the camera worker thread (should return True)
        self.assertTrue(camera.stop_worker())

        # Check Pi camera has been disconnected
        self.assertTrue(camera.camera)

        # Restart worker thread
        self.assertTrue(camera.start_worker())

        self.assertTrue(camera.camera)
        self.assertTrue(camera.thread)
        self.assertIsInstance(camera.stream, io.IOBase)


if __name__ == '__main__':
    with PiCameraStreamer() as camera:

        suites = [
            unittest.TestLoader().loadTestsFromTestCase(TestCaptureMethods),
            unittest.TestLoader().loadTestsFromTestCase(TestUnencodedMethods),
            unittest.TestLoader().loadTestsFromTestCase(TestThreadStarting),
            unittest.TestLoader().loadTestsFromTestCase(TestRecordMethods),
        ]

        alltests = unittest.TestSuite(suites)

        result = unittest.TextTestRunner(verbosity=2).run(alltests)
