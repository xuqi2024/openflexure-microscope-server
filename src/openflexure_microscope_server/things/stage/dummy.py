"""Functionality for mimicking a stage during simulation and testing."""

from __future__ import annotations

from collections.abc import Mapping
import time

import labthings_fastapi as lt

from . import BaseStage


class DummyStage(BaseStage):
    """A dummy stage for testing purposes.

    This stage should work similarly to a Sangaboard stage, but without any
    hardware attached.
    """

    def __init__(self, step_time: float = 0.001, **kwargs):
        """Initialise the Dummy stage, setting the step_time to adjust the speed.

        :param step_time: The time in seconds per "motor" step. The default of 0.001
            works well for the live simulation. For unit testing it is very slow
            so the speed can be increased. Increasing it too far is problematic if
            also doing computationally heavy tasks like simulated image blurring.
        """
        super().__init__(**kwargs)
        self.step_time = step_time

    def __enter__(self):
        """Register the stage position when the Thing context manager is opened."""
        self.instantaneous_position = self.position

    def __exit__(self, _exc_type, _exc_value, _traceback):
        """Nothing to do when the Thing context manager is closed."""

    @lt.thing_action
    def move_relative(
        self,
        cancel: lt.deps.CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make a relative move. Keyword arguments should be axis names."""
        displacement = [kwargs.get(k, 0) for k in self.axis_names]
        self.moving = True
        try:
            fraction_complete = 0.0
            dt = self.step_time
            max_displacement = max(abs(v) for v in displacement)
            start_time = time.time()
            while time.time() - start_time < dt * max_displacement:
                if block_cancellation:
                    time.sleep(dt)
                else:
                    cancel.sleep(dt)
                fraction_complete = (time.time() - start_time) / (dt * max_displacement)
                self.instantaneous_position = {
                    k: self.position[k] + int(fraction_complete * v)
                    for k, v in zip(self.axis_names, displacement)
                }
            fraction_complete = 1.0
        except lt.exceptions.InvocationCancelledError as e:
            # If the move has been cancelled, stop it but don't handle the exception.
            # We need the exception to propagate in order to stop any calling tasks,
            # and to mark the invocation as "cancelled" rather than stopped.
            raise e
        finally:
            self.moving = False
            self.position = {
                k: self.position[k] + int(fraction_complete * v)
                for k, v in zip(self.axis_names, displacement)
            }
            self.instantaneous_position = self.position

    @lt.thing_action
    def move_absolute(
        self,
        cancel: lt.deps.CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make an absolute move. Keyword arguments should be axis names."""
        displacement = {
            axis: int(pos) - self.position[axis]
            for axis, pos in kwargs.items()
            if axis in self.axis_names
        }
        self.move_relative(
            cancel, block_cancellation=block_cancellation, **displacement
        )

    @lt.thing_action
    def set_zero_position(self):
        """Make the current position zero in all axes.

        This action does not move the stage, but resets the position to zero.
        It is intended for use after manually or automatically recentring the
        stage.
        """
        self.position = dict.fromkeys(self.axis_names, 0)
        self.instantaneous_position = self.position
