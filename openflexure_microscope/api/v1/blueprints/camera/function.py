from openflexure_microscope.api.v1.views import MicroscopeView
from openflexure_microscope.api.utilities import JsonPayload

from flask import jsonify, request


class ZoomAPI(MicroscopeView):

    def get(self):
        """
        Get the current zoom value

        .. :quickref: Zoom; Get the zoom value

        :>header Accept: application/json

        :<header Content-Type: application/json
        :status 200: preview started/stopped
        """
        zoom_value = self.microscope.camera.state['zoom_value']

        return jsonify({'zoom_value': zoom_value})

    def post(self):
        """
        Change the current zoom value

        .. :quickref: Zoom; Set the zoom value

        **Example requests**:

        .. sourcecode:: http

          POST /camera/zoom HTTP/1.1
          Accept: application/json

          {
            "zoom_value": 2.5,
          }

        :>header Accept: application/json

        :<header Content-Type: application/json
        :status 200: preview started/stopped
        """
        payload = JsonPayload(request)
        zoom_value = payload.param('zoom_value', default=1.0, convert=float)

        self.microscope.camera.set_zoom(zoom_value)

        return jsonify(self.microscope.camera.state)


class OverlayAPI(MicroscopeView):

    def get(self):
        """
        Get overlay text

        .. :quickref: Overlay; Get camera overlay text

        :>header Accept: application/json

        :<header Content-Type: application/json
        :status 200: preview started/stopped
        """
        text = self.microscope.camera.camera.annotate_text
        size = self.microscope.camera.camera.annotate_text_size

        return jsonify({'text': text, 'size': size})

    def post(self):
        """
        Set overlay text

        .. :quickref: Overlay; Set camera overlay text

        **Example requests**:

        .. sourcecode:: http

          POST /camera/overlay HTTP/1.1
          Accept: application/json

          {
            "text": "2019/01/15 14:48",
            "size": 50
          }

        :>header Accept: application/json

        :<header Content-Type: application/json
        :status 200: preview started/stopped
        """

        payload = JsonPayload(request)
        text = payload.param('text', default="", convert=str)
        size = payload.param('size', default=50, convert=int)

        self.microscope.camera.camera.annotate_text = text
        self.microscope.camera.camera.annotate_text_size = size

        return jsonify({'text': text, 'size': size})
