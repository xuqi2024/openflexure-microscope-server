Capture Object
=======================================================

By default, all image and video capture data are stored to instances of :py:class:`openflexure_microscope.camera.capture.CaptureObject`. This class mostly wraps up complexity associated with moving data between disk and memory. 

The class also includes some convenience features such as handling metadata tags and file names, and generating image thumbnails. Additionally, the class handles storing capture metadata to Exif tags in supported formats. 

Below are details of available methods and attributes.

.. automodule:: openflexure_microscope.camera.capture
    :members: