from openflexure_microscope.stage.base import BaseStage
from openflexure_microscope.utilities import axes_to_array

from collections.abc import Iterable
import numpy as np
import time
import logging


class MissingStage(BaseStage):
    def __init__(self, port=None, **kwargs):
        BaseStage.__init__(self)
        self._position = [0, 0, 0]
        self._n_axis = 3
        self._backlash = None

        self.axis_names = ["x", "y", "z"]  # Assume all sangaboards are 3 axis

    @property
    def state(self):
        """The general state dictionary of the board."""
        state = {"position": self.position_map}
        return state

    @property
    def configuration(self):
        return {}

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

    @property
    def n_axes(self):
        return self._n_axis

    @property
    def position(self):
        return self._position

    @property
    def backlash(self):
        if self._backlash is not None:
            return self._backlash
        else:
            return np.array([0] * self.n_axes)

    @backlash.setter
    def backlash(self, blsh):
        if blsh is None:
            self._backlash = None
        elif isinstance(blsh, Iterable):
            assert len(blsh) == self.n_axes
            self._backlash = np.array(blsh)
        else:
            self._backlash = np.array([int(blsh)] * self.n_axes, dtype=np.int)

    def move_rel(
        self, displacement: list, axis=None, backlash=True, simulate_time: bool = True
    ):
        if simulate_time:
            time.sleep(0.5)
        if axis is not None:
            assert axis in self.axis_names, "axis must be one of {}".format(
                self.axis_names
            )
            move = np.zeros(self.n_axes, dtype=np.int)
            move[np.argmax(np.array(self.axis_names) == axis)] = int(displacement)
            displacement = move

        initial_move = np.array(displacement, dtype=np.int)

        self._position = list(np.array(self._position) + np.array(initial_move))
        logging.debug(np.array(self._position) + np.array(initial_move))
        logging.debug(f"New position: {self._position}")

    def move_abs(self, final, simulate_time: bool = True, **kwargs):
        if simulate_time:
            time.sleep(0.5)

        self._position = list(final)
        logging.debug(f"New position: {self._position}")

    def zero_position(self):
        """Set the current position to zero"""
        self._position = [0, 0, 0]

    def close(self):
        pass
