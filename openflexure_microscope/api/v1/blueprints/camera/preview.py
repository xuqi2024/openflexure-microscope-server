from openflexure_microscope.api.utilities import JsonResponse
from openflexure_microscope.api.v1.views import MicroscopeView

from flask import jsonify, request
import logging


class GPUPreviewAPI(MicroscopeView):
    def post(self, operation):
        """
        Start or stop the onboard GPU preview. 
        Optional "window" parameter can be passed to control the position and size of the preview window, 
        in the format ``[x, y, width, height]``.

        .. :quickref: GPU Preview; Start/stop preview

        **Example requests**:

        .. sourcecode:: http

          POST /camera/preview/start HTTP/1.1
          Accept: application/json

          {
            "window": [0, 0, 480, 320], 
          }

        .. sourcecode:: http

          POST /camera/preview/stop HTTP/1.1
          Accept: application/json

        :>header Accept: application/json

        :<header Content-Type: application/json
        :status 200: preview started/stopped
        """
        if operation == "start":
            payload = JsonResponse(request)

            window = payload.param("window", default=[])
            logging.debug(window)

            if len(window) != 4:
                fullscreen = True
                window = None
            else:
                fullscreen = False
                window = [int(w) for w in window]

            self.microscope.camera.start_preview(fullscreen=fullscreen, window=window)
        elif operation == "stop":
            self.microscope.camera.stop_preview()
        return jsonify(self.microscope.state)
