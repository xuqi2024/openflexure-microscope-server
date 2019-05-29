from openflexure_microscope.stage.base import BaseStage


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
            'position': {
                'x': self.position[0],
                'y': self.position[1],
                'z': self.position[2],
            },
            'board': None,
            'version': '0'
        }
        return state

    @property
    def n_axes(self):
        return self._n_axis

    @property
    def position(self):
        return self._position

    @property
    def backlash(self):
        return self._backlash if self._backlash else [0]*self.n_axes

    @backlash.setter
    def backlash(self, blsh):
        if blsh is None:
            self._backlash = None
        assert len(blsh) == self.n_axes
        self._backlash = [int(blsh)]*self.n_axes

    def move_rel(self, displacement, axis=None, backlash=True):
        pass

    def move_abs(self, final, **kwargs):
        pass

    def close(self):
        pass
