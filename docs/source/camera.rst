Camera Class
============

.. toctree::
   :maxdepth: 2

   picamera.rst
   basecamera.rst
   capture.rst

Capturing from a camera object
------------------------------

In the cases of both a Raspberry Pi Streaming Camera, and a Mock Camera (attached if no real camera can be found), the camera's ``capture`` method takes as it's first positional argument either a string describing a file path to save to, or any Python file-like object.

The :class:`openflexure_microscope.camera.capture.CaptureObject` class works by providing a file path string, but adds additional functionality around storing and retreiving EXIF metadata in compatible files.

If, for your application, you do not require this functionality, you can pass a simple string or file-like object. For example, to take an image that will be stored in-memory, processed rapidly, and then discarded, you could use a BytesIO stream:

.. code-block:: python

    import io
    from PIL import Image
    ...

    with microscope.camera.lock, io.BytesIO() as stream:

        microscope.camera.capture(
            stream,
            use_video_port=True,
            bayer=False,
        )

        stream.seek(0)
        image = Image.open(stream)