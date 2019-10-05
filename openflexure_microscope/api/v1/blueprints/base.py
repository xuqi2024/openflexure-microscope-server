from openflexure_microscope.api.utilities import gen, JsonResponse
from openflexure_microscope.api.v1.views import MicroscopeView

from flask import Response, Blueprint, jsonify, request
import logging


class StreamAPI(MicroscopeView):
    def get(self):
        """
        Real-time MJPEG stream from the microscope camera

        .. :quickref: State; Camera stream

        :>header Accept: image/jpeg
        :>header Content-Type: image/jpeg
        :status 200: stream active
        """
        # Restart stream worker thread
        self.microscope.camera.start_worker()

        return Response(
            gen(self.microscope.camera),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )


class SnapshotAPI(MicroscopeView):
    def get(self):
        """
        Single snapshot from the camera stream

        .. :quickref: State; Camera snapshot

        :>header Accept: image/jpeg
        :>header Content-Type: image/jpeg
        :status 200: stream active
        """
        # Restart stream worker thread
        self.microscope.camera.start_worker()

        return Response(
            self.microscope.camera.get_frame(),
            mimetype="image/jpeg",
        )

class StateAPI(MicroscopeView):
    def get(self):
        """
        JSON representation of the microscope object.

        .. :quickref: State; Microscope state

        **Example request**:

        .. sourcecode:: http

          GET /state/ HTTP/1.1
          Accept: application/json

        **Example response**:

        .. sourcecode:: http

          HTTP/1.1 200 OK
          Vary: Accept
          Content-Type: application/json

          {
            "camera": {
                "preview_active": false, 
                "record_active": false, 
                "stream_active": true
            }, 
            "plugin": {}, 
            "stage": {
                "backlash": {
                    "x": 128, 
                    "y": 128, 
                    "z": 128
                }, 
                "position": {
                    "x": -8080, 
                    "y": 5665, 
                    "z": -12600
                }
            }
          }

        :>header Accept: application/json
        :>header Content-Type: application/json
        :status 200: state available
        """
        return jsonify(self.microscope.state)


class ConfigAPI(MicroscopeView):
    def get(self):
        """
        JSON representation of the microscope config.

        .. :quickref: Config; Get microscope config

        **Example request**:

        .. sourcecode:: http

          GET /config/ HTTP/1.1
          Accept: application/json

        **Example response**:

        .. sourcecode:: http

          HTTP/1.1 200 OK
          Vary: Accept
          Content-Type: application/json

          {
            "id": "0e2c6fac5421429aac67c7903107bdd8", 
            "name": "docuscope-2000",
            "fov": [4100, 3146],
            "camera_settings": {
                "image_resolution": [2592, 1944], 
                "numpy_resolution": [1312, 976], 
                "video_resolution": [832, 624],
                "jpeg_quality": 75, 
                "picamera_settings": {
                    "analog_gain": 1.0, 
                    "digital_gain": 1.0, 
                    "awb_gains": [0.92578125, 2.94921875], 
                    "awb_mode": "off", 
                    "exposure_mode": "off", 
                    "framerate": 24.0, 
                    "saturation": 0, 
                    "shutter_speed": 5378
                }, 
            },
            "stage_settings": {
                "backlash": {
                    "x": 256,
                    "y": 256,
                    "z": 0
                }
            }
            "plugins": [
                "openflexure_microscope.plugins.default.autofocus:AutofocusPlugin",
                "openflexure_microscope.plugins.default.scan:ScanPlugin",
                "openflexure_microscope.plugins.default.camera_calibration:Plugin"
            ]
          }

        :>header Accept: application/json
        :>header Content-Type: application/json
        :status 200: state available
        """
        return jsonify(self.microscope.read_config(json_safe=True))

    def post(self):
        """
        Modify microscope configuration

        .. :quickref: Config; Set microscope config

        **Example request**:

        .. sourcecode:: http

          POST /config HTTP/1.1
          Accept: application/json

          {
            "id": "0e2c6fac5421429aac67c7903107bdd8", 
            "name": "docuscope-2000",
            "fov": [4100, 3146],
            "camera_settings": {
                "image_resolution": [2592, 1944], 
                "numpy_resolution": [1312, 976], 
                "video_resolution": [832, 624],
                "jpeg_quality": 75, 
                "picamera_settings": {
                    "analog_gain": 1.0, 
                    "digital_gain": 1.0, 
                    "awb_gains": [0.92578125, 2.94921875], 
                    "awb_mode": "off", 
                    "exposure_mode": "off", 
                    "framerate": 24.0, 
                    "saturation": 0, 
                    "shutter_speed": 5378
                }, 
            },
            "stage_settings": {
                "backlash": {
                    "x": 256,
                    "y": 256,
                    "z": 0
                }
            }
            "plugins": [
                "openflexure_microscope.plugins.default.autofocus:AutofocusPlugin",
                "openflexure_microscope.plugins.default.scan:ScanPlugin",
                "openflexure_microscope.plugins.default.camera_calibration:Plugin"
            ]
          }

        :>header Accept: application/json

        :<json string id: Unique string identifier of the microscope.
        :<json string name: Friendly name for the microscope
        :<json array fov: Field of view (motor steps per full width and height of frame)
        :<json json camera_settings:    - **image_resolution** *(array)*: Resolution of full image captures
                                        - **numpy_resolution** *(array)*: Resolution of full numpy array captures
                                        - **video_resolution** *(array)*: Resolution of video recordings, low res image captures, and the preview stream
                                        - **jpeg_quality** *(int)*: Quality in which to store JPEG capture data
                                        - **picamera_settings** *(json)*: Key-value pairs to apply directly to any attached PiCamera object
        :<json json stage_settings:     - **backlash** *(json)*: x, y, and z backlash compensation, in motor steps
        :<json array plugins: Array of plugin paths to load. Requires reloading the microscope object after applying

        :<header Content-Type: application/json
        :status 200: capture created

        """
        payload = JsonResponse(request)

        logging.debug("Updating settings from POST request:")
        logging.debug(payload.json)

        self.microscope.apply_config(payload.json)
        self.microscope.save_config()

        return jsonify(self.microscope.read_config(json_safe=True))


def construct_blueprint(microscope_obj):

    blueprint = Blueprint("base_blueprint", __name__)

    blueprint.add_url_rule(
        "/stream", view_func=StreamAPI.as_view("stream", microscope=microscope_obj)
    )

    blueprint.add_url_rule(
        "/snapshot", view_func=SnapshotAPI.as_view("snapshot", microscope=microscope_obj)
    )

    blueprint.add_url_rule(
        "/state", view_func=StateAPI.as_view("state", microscope=microscope_obj)
    )

    blueprint.add_url_rule(
        "/config", view_func=ConfigAPI.as_view("config", microscope=microscope_obj)
    )

    return blueprint
