from openflexure_microscope.devel import MicroscopeViewPlugin, TaskDeniedException, JsonPayload, Response, request, escape, jsonify

import logging

class DoAPI(MicroscopeViewPlugin):
    """
    A simple example API plugin
    """

    def get(self):
        return jsonify(self.plugin.get_values_dict())

    def post(self):
        # Get payload JSON
        payload = JsonPayload(request)

        # Extract a values from the JSON payload.
        val_int = payload.param('val_int', default=None, convert=int)
        val_str = payload.param('val_str', default=None, convert=str)
        val_radio = payload.param('val_radio', default=None)
        val_check = payload.param('val_check', default=None)
        val_select = payload.param('val_select', default=None)
        val_disposable = payload.param('val_disposable', default=None)

        self.plugin.set_values(
            val_int,
            val_str,
            val_radio,
            val_check,
            val_select,
            val_disposable
        )

        print(self.plugin.get_values_dict())

        return jsonify({
            'response': 'completed'
        })

class TaskAPI(MicroscopeViewPlugin):
    """
    A task example API plugin
    """

    def get(self):
        return jsonify({
            'run_time': self.plugin.run_time
        })

    def post(self):
        # Get payload JSON
        payload = JsonPayload(request)

        # Extract a values from the JSON payload.
        val_int = payload.param('run_time', default=5, convert=int)

        logging.info("Running task...")
        task = self.microscope.task.start(self.plugin.generate_random_numbers_for_a_while, val_int)

        # return a handle on the autofocus task
        return jsonify(task.state), 202