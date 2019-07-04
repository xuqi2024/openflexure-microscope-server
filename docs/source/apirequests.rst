Introduction
------------

In these examples, our microscope is located at the IP ``192.168.1.126``, running on port 5000.


New Image Capture
-----------------

Temprary capture, using video port.

CURL
++++
.. code-block:: none

   curl -X POST -H "Content-Type: application/json" -d \\
   '{"temporary": true, "use_video_port": true}' http://192.168.1.126:5000/api/v1/camera/capture

HTTPie
++++++
.. code-block:: none

   http POST http://192.168.1.126:5000/api/v1/camera/capture temporary:=true use_video_port:=true

Python Requests
+++++++++++++++
.. code-block:: python

   json_payload = {
        "keep_on_disk": keep_on_disk,
        "use_video_port": use_video_port
   }
   requests.post('http://192.168.1.126:5000/api/v1/camera/capture', json=json_payload)

Update Config
-------------

Example, changing picamera shutter speed to 2000, and the JPEG quality to 90.

CURL
++++
.. code-block:: none

   curl -X POST -H "Content-Type: application/json" -d \\
   '{"camera_settings": {"picamera_settings": {"shutter_speed": 2000}, "jpeg_quality": 90}}' http://192.168.1.126:5000/api/v1/config

HTTPie
++++++
.. code-block:: none

   http POST http://192.168.1.126:5000/api/v1/config camera_settings:='{"jpeg_quality": 90, "picamera_settings": {"shutter_speed": 2000}}' 

Python Requests
+++++++++++++++
.. code-block:: python

   json_payload = {
       camera_settings: {
            "jpeg_quality": 90,
            "picamera_settings": {"shutter_speed": 2000}
        }
   }
   requests.post('http://192.168.1.126:5000/api/v1/config', json=json_payload)

Read Config
-----------

CURL
++++
.. code-block:: none

   curl http://192.168.1.126:5000/api/v1/config

HTTPie
++++++
.. code-block:: none

   http GET http://192.168.1.126:5000/api/v1/config

Python Requests
+++++++++++++++
.. code-block:: python

   requests.get('http://192.168.1.126:5000/api/v1/config')

Recalibrate Picamera
--------------------

Starts the automatic recalibration plugin

CURL
++++
.. code-block:: none

   curl -X POST -H "Content-Type: application/json" \\
   http://192.168.1.126:5000/api/v1/plugin/default/camera_calibration/recalibrate

HTTPie
++++++
.. code-block:: none

   http POST http://192.168.1.126:5000/api/v1/plugin/default/camera_calibration/recalibrate

Python Requests
+++++++++++++++
.. code-block:: python

   requests.post('http://192.168.1.126:5000/api/v1/plugin/default/camera_calibration/recalibrate')