from __future__ import annotations
from typing import TypeAlias
from collections.abc import Sequence, Mapping

import labthings_fastapi as lt


class BaseStage(lt.Thing):
    """A base stage class for OpenFlexure translation stages

    This can't be used directly but should reduce boilerplate code when
    implementing new stages. A minimal working stage must implement
    `move_relative` and `move_absolute` actions, which update the
    `position` property on completion, and provide `set_zero_position`.
    """

    _axis_names = ("x", "y", "z")

    @lt.thing_property
    def axis_names(self) -> Sequence[str]:
        """The names of the stage's axes, in order."""
        return self._axis_names

    position = lt.ThingProperty(
        Mapping[str, int],
        dict.fromkeys(_axis_names, 0),
        description="Current position of the stage",
        readonly=True,
        observable=True,
    )

    moving = lt.ThingProperty(
        bool,
        False,
        description="Whether the stage is in motion",
        readonly=True,
        observable=True,
    )

    @property
    def thing_state(self):
        """Summary metadata describing the current state of the stage"""
        return {"position": self.position}

    @lt.thing_action
    def move_relative(
        self,
        cancel: lt.deps.CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make a relative move. Keyword arguments should be axis names."""
        raise NotImplementedError(
            "StageThings must define their own move_relative method"
        )

    @lt.thing_action
    def move_absolute(
        self,
        cancel: lt.deps.CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make an absolute move. Keyword arguments should be axis names."""
        raise NotImplementedError(
            "StageThings must define their own move_absolute method"
        )

    @lt.thing_action
    def set_zero_position(self):
        """Make the current position zero in all axes

        This action does not move the stage, but resets the position to zero.
        It is intended for use after manually or automatically recentring the
        stage.
        """
        raise NotImplementedError(
            "StageThings must define their own set_zero_position method"
        )


StageDependency: TypeAlias = lt.deps.direct_thing_client_dependency(
    BaseStage, "/stage/"
)
