from openflexure_microscope.api.utilities import JsonResponse
from labthings.server.view import View
from labthings.server.find import find_component
from labthings.server.decorators import use_args, marshal_with, doc, ThingAction
from labthings.server import fields

from openflexure_microscope.utilities import axes_to_array, filter_dict

from flask import Blueprint, jsonify, request

import logging


@ThingAction
class MoveStageAPI(View):
    @use_args(
        {
            "absolute": fields.Boolean(
                default=False, example=False, description="Move to an absolute position"
            ),
            "x": fields.Int(default=0, example=100),
            "y": fields.Int(default=0, example=100),
            "z": fields.Int(default=0, example=20),
        }
    )
    def post(self, args):
        """
        Move the microscope stage in x, y, z
        """
        microscope = find_component("org.openflexure.microscope")

        # Handle absolute positioning (calculate a relative move from current position and target)
        if (args.get("absolute")) and (microscope.stage):  # Only if stage exists
            target_position = axes_to_array(args, ["x", "y", "z"])
            logging.debug("TARGET: {}".format(target_position))
            position = [
                target_position[i] - microscope.stage.position[i] for i in range(3)
            ]
            logging.debug("DELTA: {}".format(position))

        else:
            # Get coordinates from payload
            position = axes_to_array(args, ["x", "y", "z"], [0, 0, 0])

        logging.debug(position)

        # Move if stage exists
        if microscope.stage:
            # Explicitally acquire lock
            with microscope.stage.lock:
                microscope.stage.move_rel(position)
        else:
            logging.warning("Unable to move. No stage found.")

        # TODO: Make schema for microscope state
        return jsonify(microscope.state["stage"]["position"])


@ThingAction
class ZeroStageAPI(View):
    def post(self):
        """
        Zero the stage coordinates.
        Does not move the stage, but rather makes the current position read as [0, 0, 0]
        """
        microscope = find_component("org.openflexure.microscope")
        microscope.stage.zero_position()

        # TODO: Make schema for microscope state
        return jsonify(microscope.state["stage"])
