from __future__ import annotations
import logging
import threading
import time
from typing import Iterator, Literal
from contextlib import contextmanager
from collections.abc import Mapping

import sangaboard
import labthings_fastapi as lt

from . import BaseStage


class SangaboardThing(BaseStage):
    """A Thing to manage a Sangaboard motor controller.

    Internally, this uses the ``pysangaboard`` package from PyPi. This imports
    as ``sangaboard``. As ``pysangaboard`` does not support some features added
    to the Sangaboard firmware v1 (LED flashing, aborting moves, etc) this
    functionality is accessed by directly querying the serial interface.
    """

    def __init__(self, port: str = None, **kwargs):
        """Initialise SangaboardThing.

        Initialise the "Thing", but do not initialise an underlying
        ``Sangaboard`` object from ``pysangaboard`` until the Thing context
        manager is started.

        :param port: The serial port for the Sangaboard. Optional, this is used
            to stop the Sangaboard object querying available devices.
        :param ``**kwargs``: Any other keyword arguments to be passed to the
            Sangaboard class

        """
        self.sangaboard_kwargs = kwargs
        self.sangaboard_kwargs["port"] = port

    def __enter__(self):
        self._sangaboard = sangaboard.Sangaboard(**self.sangaboard_kwargs)
        self._sangaboard_lock = threading.RLock()
        with self.sangaboard() as sb:
            if sb.version_tuple[0] != 1:
                raise RuntimeError(
                    "Please update your Sangaboard Firmware. v1 is required."
                )
            sb.query("blocking_moves false")
        self.update_position()

    def __exit__(self, _exc_type, _exc_value, _traceback):
        with self.sangaboard() as sb:
            sb.close()

    @contextmanager
    def sangaboard(self) -> Iterator[sangaboard.Sangaboard]:
        """Return the wrapped ``sangaboard.Sangaboard`` instance.

        This is protected by a ``threading.RLock``, which may change in future.
        """
        with self._sangaboard_lock:
            yield self._sangaboard

    def update_position(self) -> None:
        """Read position from the stage and set the corresponding property."""
        with self.sangaboard() as sb:
            self.position = dict(zip(self.axis_names, sb.position))

    @lt.thing_action
    def move_relative(
        self,
        cancel: lt.deps.CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ) -> None:
        """Make a relative move. Keyword arguments should be axis names."""
        displacement = [kwargs.get(axis, 0) for axis in self.axis_names]
        with self.sangaboard() as sb:
            self.moving = True
            try:
                sb.move_rel(displacement)
                if block_cancellation:
                    sb.query("notify_on_stop")
                else:
                    while sb.query("moving?") == "true":
                        cancel.sleep(0.1)
            except lt.exceptions.InvocationCancelledError as e:
                # If the move has been cancelled, stop it but don't handle the exception.
                # We need the exception to propagate in order to stop any calling tasks,
                # and to mark the invocation as "cancelled" rather than stopped.
                sb.query("stop")
                raise e
            finally:
                self.moving = False
                self.update_position()

    @lt.thing_action
    def move_absolute(
        self,
        cancel: lt.deps.CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ) -> None:
        """Make an absolute move. Keyword arguments should be axis names."""
        with self.sangaboard():
            self.update_position()
            displacement = {
                axis: int(pos) - self.position[axis]
                for axis, pos in kwargs.items()
                if axis in self.axis_names
            }
            self.move_relative(
                cancel, block_cancellation=block_cancellation, **displacement
            )

    @lt.thing_action
    def set_zero_position(self) -> None:
        """Make the current position zero in all axes.

        This action does not move the stage, but resets the position to zero.
        It is intended for use after manually or automatically recentring the
        stage.
        """
        with self.sangaboard() as sb:
            sb.zero_position()
        self.update_position()

    @lt.thing_action
    def flash_led(
        self,
        number_of_flashes: int = 10,
        dt: float = 0.5,
        led_channel: Literal["cc"] = "cc",
    ) -> None:
        """Flash the LED to identify the board.

        This is intended to be useful in situations where there are multiple
        Sangaboards in use, and it is necessary to identify which one is
        being addressed.
        """
        led_command = f"led_{led_channel}"
        with self.sangaboard() as sb:
            return_value = sb.query(f"{led_command}?")
            if not return_value.startswith("CC LED:"):
                raise IOError("The sangaboard does not support LED control")

            # Reading and setting LED brightness suffers from repeated reads and writes
            # decreasing the value. Rather than use the value the code warns that the value
            # cannot be used.
            intended_brightness = float(return_value[7:])
            on_brightness = 0.32
            logging.warning(
                "Brightness control is not yet implemented. Desired brightness: "
                f"{intended_brightness}. Set brightness: {on_brightness}"
            )
            for i in range(number_of_flashes):
                sb.query(f"{led_command} 0")
                time.sleep(dt)
                sb.query(f"{led_command} {on_brightness}")
                time.sleep(dt)
