import logging

from labthings import fields, find_component
from labthings.views import ActionView


class MoveStageAPI(ActionView):
    args = {
        "absolute": fields.Boolean(
            load_default=False,
            metadata={"description": "Move to an absolute position", "example": False},
        ),
        "x": fields.Int(load_default=None, metadata={"example": 100}, allow_none=True),
        "y": fields.Int(load_default=None, metadata={"example": 100}, allow_none=True),
        "z": fields.Int(load_default=None, metadata={"example": 20}, allow_none=True),
    }

    def post(self, args):
        """
        Move the microscope stage in x, y, z

        This action moves the stage. Any axes that are not specifed will not move.
        If `absolute=True` is specified, the stage will move to the absolute
        coordinates given.  If not (the default), a relative move is made, i.e.
        `x=0, y=0, z=0` corresponds to no motion.
        """
        microscope = find_component("org.openflexure.microscope")

        if not microscope.stage:
            logging.warning("Unable to move. No stage found.")
            return microscope.state["stage"]["position"]

        absolute_move = args.get("absolute")
        move = [0, 0, 0]  # Default to no motion
        for i, axis in enumerate(["x", "y", "z"]):
            if axis in args and args[axis] is not None:
                if absolute_move:
                    # We emulate absolute moves by calculating a relative move that
                    # will take us to the right position.
                    move[i] = args[axis] - microscope.stage.position[i]
                else:
                    move[i] = args[axis]

        logging.debug(f"Moving stage by {move}, request was {args}")

        # Explicitly acquire lock with 1s timeout
        with microscope.stage.lock(timeout=1):
            microscope.stage.move_rel(move)

        return microscope.state["stage"]["position"]


class ZeroStageAPI(ActionView):
    def post(self):
        """
        Zero the stage coordinates.

        This action does not move the stage, but rather makes the current position read as [0, 0, 0]
        """
        microscope = find_component("org.openflexure.microscope")

        with microscope.stage.lock(timeout=1):
            microscope.stage.zero_position()

        return microscope.state["stage"]
