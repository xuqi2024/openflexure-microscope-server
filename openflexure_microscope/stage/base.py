from abc import ABCMeta, abstractmethod
from openflexure_microscope.lock import StrictLock


class BaseStage(metaclass=ABCMeta):
    """
    Attributes:
        lock (:py:class:`openflexure_microscope.lock.StrictLock`): Strict lock controlling thread
            access to camera hardware
    """
    def __init__(self):
        self.lock = StrictLock(timeout=5)

    @abstractmethod
    def apply_config(self, config: dict):
        """Update settings from a config dictionary"""
        pass

    @abstractmethod
    def read_config(self):
        """Return the current settings as a dictionary"""
        pass

    @property
    @abstractmethod
    def state(self):
        """The general state dictionary of the board.
        Should at least contain 'position', and 'board' keys.
        Note: A None/Null value for 'board' will disable stage
        movement in the OpenFlexure eV client software,
        """
        pass

    @property
    @abstractmethod
    def n_axes(self):
        """The number of axes this stage has."""
        pass

    @property
    @abstractmethod
    def position(self):
        """The current position, as a list"""
        pass

    @property
    @abstractmethod
    def backlash(self):
        """Get the distance used for backlash compensation."""
        pass

    @backlash.setter
    @abstractmethod
    def backlash(self):
        """Set the distance used for backlash compensation."""
        pass

    @abstractmethod
    def move_rel(self, displacement, backlash=True):
        """Make a relative move, optionally correcting for backlash.
        displacement: integer or array/list of 3 integers
        backlash: (default: True) whether to correct for backlash.
        """
        pass

    @abstractmethod
    def move_abs(self, final, **kwargs):
        """Make an absolute move to a position"""
        pass

    @abstractmethod
    def close(self):
        """Cleanly close communication with the stage"""
        pass
