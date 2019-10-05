from openflexure_microscope.api.utilities import JsonResponse
from openflexure_microscope.api.v1.views import MicroscopeView
from openflexure_microscope.utilities import axes_to_array, filter_dict

from flask import Blueprint, jsonify, request

import logging


class PositionAPI(MicroscopeView):
    def get(self):
        """
        Return current x, y and z positions of the stage. 
        The response is formatted as a sub-section of the general microscope state.

        .. :quickref: Position; Get current position

        **Example request**:

        .. sourcecode:: http

          GET /stage/position/ HTTP/1.1
          Accept: application/json

        **Example response**:

        .. sourcecode:: http

          HTTP/1.1 200 OK
          Vary: Accept
          Content-Type: application/json

          {
            "stage": {
                "position": {
                "x": -6629, 
                "y": 7489, 
                "z": -3844
                }
            }
          }

        """
        out = filter_dict(self.microscope.state, ["stage", "position"])
        return jsonify(out)

    def post(self):
        """
        Set x, y and z positions of the stage.

        .. :quickref: Position; Update current position

        :reqheader Accept: application/json
        :<json boolean absolute: (true) move to absolute position, (false) move by relative amount
        :<json boolean force: allow moving by more than programmed limit
        :<json int x: x steps
        :<json int y: y steps
        :<json int z: z steps

        """
        # Create response object
        payload = JsonResponse(request)
        logging.debug(payload.json)

        # Construct position array
        position = [0, 0, 0]

        # Handle absolute positioning (calculate a relative move from current position and target)
        if (payload.param("absolute") is True) and (
            self.microscope.stage
        ):  # Only if stage exists
            target_position = axes_to_array(payload.json, ["x", "y", "z"])
            logging.debug("TARGET: {}".format(target_position))
            position = [
                target_position[i] - self.microscope.stage.position[i] for i in range(3)
            ]
            logging.debug("DELTA: {}".format(position))

        else:
            # Get coordinates from payload
            position = axes_to_array(payload.json, ["x", "y", "z"], [0, 0, 0])

        logging.debug(position)

        # Move if stage exists
        if self.microscope.stage:
            # Explicitally acquire lock
            with self.microscope.stage.lock:
                self.microscope.stage.move_rel(position)

        out = filter_dict(self.microscope.state, ["stage", "position"])

        return jsonify(out)


def construct_blueprint(microscope_obj):

    blueprint = Blueprint("stage_blueprint", __name__)

    blueprint.add_url_rule(
        "/position",
        view_func=PositionAPI.as_view("position", microscope=microscope_obj),
    )

    return blueprint
