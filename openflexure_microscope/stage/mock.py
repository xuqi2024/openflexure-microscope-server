from openflexure_microscope.stage.base import BaseStage
from openflexure_microscope.utilities import axes_to_array

from collections.abc import Iterable
import numpy as np


class MockStage(BaseStage):
    def __init__(self, port=None, **kwargs):
        BaseStage.__init__(self)
        self._position = [0, 0, 0]
        self._n_axis = 3
        self._backlash = None

    @property
    def state(self):
        """The general state dictionary of the board."""
        state = {
            "position": {
                "x": self.position[0],
                "y": self.position[1],
                "z": self.position[2],
            },
            "board": None,
            "version": "0",
        }
        return state

    def apply_config(self, config: dict):
        """Update settings from a config dictionary"""

        # Set backlash. Expects a dictionary with axis labels
        if "backlash" in config:
            # Construct backlash array
            backlash = axes_to_array(config["backlash"], ["x", "y", "z"], [0, 0, 0])
            self.backlash = backlash

    def read_config(self) -> dict:
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

    def move_rel(self, displacement, axis=None, backlash=True):
        pass

    def move_abs(self, final, **kwargs):
        pass

    def close(self):
        pass
