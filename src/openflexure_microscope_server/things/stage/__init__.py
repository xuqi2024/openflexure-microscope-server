from __future__ import annotations
from typing import TypeAlias
from collections.abc import Sequence, Mapping

from labthings_fastapi.descriptors.property import PropertyDescriptor
from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.dependencies.invocation import CancelHook
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency


class BaseStage(Thing):
    """A base stage class for OpenFlexure translation stages

    This can't be used directly but should reduce boilerplate code when
    implementing new stages. A minimal working stage must implement
    `move_relative` and `move_absolute` actions, which update the
    `position` property on completion, and provide `set_zero_position`.
    """

    _axis_names = ("x", "y", "z")

    @thing_property
    def axis_names(self) -> Sequence[str]:
        """The names of the stage's axes, in order."""
        return self._axis_names

    position = PropertyDescriptor(
        Mapping[str, int],
        dict.fromkeys(_axis_names, 0),
        description="Current position of the stage",
        readonly=True,
        observable=True,
    )

    moving = PropertyDescriptor(
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

    @thing_action
    def move_relative(
        self,
        cancel: CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make a relative move. Keyword arguments should be axis names."""
        raise NotImplementedError(
            "StageThings must define their own move_relative method"
        )

    @thing_action
    def move_absolute(
        self,
        cancel: CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make an absolute move. Keyword arguments should be axis names."""
        raise NotImplementedError(
            "StageThings must define their own move_absolute method"
        )

    @thing_action
    def set_zero_position(self):
        """Make the current position zero in all axes

        This action does not move the stage, but resets the position to zero.
        It is intended for use after manually or automatically recentring the
        stage.
        """
        raise NotImplementedError(
            "StageThings must define their own set_zero_position method"
        )


StageDependency: TypeAlias = direct_thing_client_dependency(BaseStage, "/stage/")
