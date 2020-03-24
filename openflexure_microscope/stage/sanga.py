import numpy as np
import time
import logging
from collections.abc import Iterable
from .sangaboard import Sangaboard
from openflexure_microscope.stage.base import BaseStage
from openflexure_microscope.utilities import axes_to_array


class SangaStage(BaseStage):
    """
    Sangaboard v0.2 and v0.3 powered Stage object

    Args:
        port (str): Serial port on which to open communication

    Attributes:
        board (:py:class:`openflexure_microscope.stage.sangaboard.Sangaboard`): Parent Sangaboard object.
        _backlash (list): 3-element (element-per-axis) list of backlash compensation in steps.
    """

    def __init__(self, port=None, **kwargs):
        """Class managing serial communications with the motors for an Openflexure stage"""
        BaseStage.__init__(self)

        self.port = port
        self.board = Sangaboard(port, **kwargs)

        self._backlash = (
            None
        )  # Initialise backlash storage, used by property setter/getter
        self.axis_names = ["x", "y", "z"]  # Assume all sangaboards are 3 axis

    @property
    def state(self):
        """The general state dictionary of the board."""
        return {"position": self.position_map}

    @property
    def configuration(self):
        return {
            "port": self.port,
            "board": self.board.board,
            "firmware": self.board.firmware,
        }

    @property
    def n_axes(self):
        """The number of axes this stage has."""
        return len(self.board.axis_names)

    @property
    def position(self):
        return self.board.position

    @property
    def backlash(self):
        """The distance used for backlash compensation.
        Software backlash compensation is enabled by setting this property to a value
        other than `None`.  The value can either be an array-like object (list, tuple,
        or numpy array) with one element for each axis, or a single integer if all axes
        are the same.
        The property will always return an array with the same length as the number of
        axes.
        The backlash compensation algorithm is fairly basic - it ensures that we always
        approach a point from the same direction.  For each axis that's moving, the
        direction of motion is compared with ``backlash``.  If the direction is opposite,
        then the stage will overshoot by the amount in ``-backlash[i]`` and then move
        back by ``backlash[i]``.  This is computed per-axis, so if some axes are moving
        in the same direction as ``backlash``, they won't do two moves.
        """
        if self._backlash is not None:
            return self._backlash
        else:
            return np.array([0] * self.n_axes)

    @backlash.setter
    def backlash(self, blsh):
        logging.debug("Setting backlash to {}".format(blsh))
        if blsh is None:
            self._backlash = None
        elif isinstance(blsh, Iterable):
            assert len(blsh) == self.n_axes
            self._backlash = np.array(blsh)
        else:
            self._backlash = np.array([int(blsh)] * self.n_axes, dtype=np.int)

    def update_settings(self, config: dict):
        """Update settings from a config dictionary"""

        # Set backlash. Expects a dictionary with axis labels
        if "backlash" in config:
            # Construct backlash array
            backlash = axes_to_array(config["backlash"], ["x", "y", "z"], [0, 0, 0])
            self.backlash = backlash

    def read_settings(self) -> dict:
        """Return the current settings as a dictionary"""
        blsh = self.backlash.tolist()
        config = {"backlash": {"x": blsh[0], "y": blsh[1], "z": blsh[2]}}

        return config

    def move_rel(self, displacement: list, axis=None, backlash=True):
        """Make a relative move, optionally correcting for backlash.
        displacement: integer or array/list of 3 integers
        axis: None (for 3-axis moves) or one of 'x','y','z'
        backlash: (default: True) whether to correct for backlash.
        """
        with self.lock:
            if not backlash or self.backlash is None:
                return self.board.move_rel(displacement, axis=axis)

            if axis is not None:
                # backlash correction is easier if we're always in 3D
                # so this code just converts single-axis moves into all-axis moves.
                assert axis in self.axis_names, "axis must be one of {}".format(
                    self.axis_names
                )
                move = np.zeros(self.n_axes, dtype=np.int)
                move[np.argmax(np.array(self.axis_names) == axis)] = int(displacement)
                displacement = move

            initial_move = np.array(displacement, dtype=np.int)
            # Backlash Correction
            # This backlash correction strategy ensures we're always approaching the
            # end point from the same direction, while minimising the amount of extra
            # motion.  It's a good option if you're scanning in a line, for example,
            # as it will kick in when moving to the start of the line, but not for each
            # point on the line.
            # For each axis where we're moving in the *opposite*
            # direction to self.backlash, we deliberately overshoot:
            initial_move -= np.where(
                self.backlash * displacement < 0,
                self.backlash,
                np.zeros(self.n_axes, dtype=self.backlash.dtype),
            )
            self.board.move_rel(initial_move)
            if np.any(displacement - initial_move != 0):
                # If backlash correction has kicked in and made us overshoot, move
                # to the correct end position (i.e. the move we were asked to make)
                self.board.move_rel(displacement - initial_move)

    def move_abs(self, final, **kwargs):
        """Make an absolute move to a position
        """
        with self.lock:
            self.board.move_abs(final, **kwargs)

    def zero_position(self):
        """Set the current position to zero"""
        with self.lock:
            self.board.zero_position()

    def close(self):
        """Cleanly close communication with the stage"""
        if hasattr(self, "board"):
            self.board.close()

    # Methods specific to Sangaboard
    def release_motors(self):
        """De-energise the stepper motor coils"""
        self.board.release_motors()

    def __enter__(self):
        """When we use this in a with statement, remember where we started."""
        self._position_on_enter = self.position
        return self

    def __exit__(self, type, value, traceback):
        """The end of the with statement.  Reset position if it went wrong.
        NB the instrument is closed when the object is deleted, so we don't
        need to worry about that here.
        """
        if type is not None:
            print(
                "An exception occurred inside a with block, resetting position \
                to its value at the start of the with block"
            )
            try:
                time.sleep(0.5)
                self.move_abs(self._position_on_enter)
            except Exception as e:
                print(
                    "A further exception occurred when resetting position: {}".format(e)
                )
            print("Move completed, raising exception...")
            raise value  # Propagate the exception
