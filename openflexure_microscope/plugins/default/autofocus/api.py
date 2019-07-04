import numpy as np
import logging

from openflexure_microscope.devel import MicroscopeViewPlugin, JsonPayload, request, jsonify

class MeasureSharpnessAPI(MicroscopeViewPlugin):
    def post(self):
        payload = JsonPayload(request)
        return jsonify({'sharpness': self.plugin.measure_sharpness()})


class AutofocusAPI(MicroscopeViewPlugin):
    def post(self):
        payload = JsonPayload(request)
        
        # Figure out the range of z values to use
        dz = payload.param("dz", default=np.linspace(-300, 300, 7), convert=np.array)

        logging.info("Running autofocus...")
        task = self.microscope.task.start(self.plugin.autofocus, dz)

        # return a handle on the autofocus task
        return jsonify(task.state), 202

class FastAutofocusAPI(MicroscopeViewPlugin):
    def post(self):
        payload = JsonPayload(request)
        
        # Figure out the parameters to use
        dz = payload.param("dz", default=2000, convert=int)
        backlash = payload.param("backlash", default=0, convert=int)
        if backlash < 0:
            backlash = 0

        logging.info("Running autofocus...")
        task = self.microscope.task.start(self.plugin.fast_autofocus, dz, backlash=backlash)

        # return a handle on the autofocus task
        return jsonify(task.state), 202