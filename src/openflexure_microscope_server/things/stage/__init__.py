from __future__ import annotations
from typing import Any, Protocol, TypeAlias, runtime_checkable
from labthings_fastapi.descriptors.property import PropertyDescriptor
from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.dependencies.invocation import CancelHook
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from collections.abc import Sequence, Mapping


@runtime_checkable
class StageProtocol(Protocol):
    """A protocol for the OpenFlexure translation stage"""

    _axis_names: Sequence[str]

    @property
    def axis_names(self) -> Sequence[str]:
        """The names of the stage's axes, in order."""
        ...

    @property
    def position(self) -> Mapping[str, int]:
        """Current position of the stage"""
        ...

    @property
    def moving() -> bool:
        "Whether the stage is in motion"
        ...

    @property
    def thing_state(self) -> Mapping[str, Any]:
        """Summary metadata describing the current state of the stage"""
        ...

    def move_relative(
        self,
        cancel: CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make a relative move. Keyword arguments should be axis names."""
        ...

    def move_absolute(
        self,
        cancel: CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make an absolute move. Keyword arguments should be axis names."""
        ...

    def set_zero_position(self):
        """Make the current position zero in all axes

        This action does not move the stage, but resets the position to zero.
        It is intended for use after manually or automatically recentring the
        stage.
        """
        ...


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
        {k: 0 for k in _axis_names},
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


class StageStub(BaseStage):
    """A Stub Thing for the OpenFlexure translation stage

    As of LabThings-FastAPI 0.0.7, we can't make a thing client dependency
    based on a protocol, because the protocol is not a Thing, and its
    methods/properties are not decorated as Affordances. This stub class
    is a workaround for that limitation, and should not be used directly.
    """

    @thing_action
    def move_relative(
        self,
        cancel: CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make a relative move. Keyword arguments should be axis names."""
        raise NotImplementedError("StageStub should not be used directly")

    @thing_action
    def move_absolute(
        self,
        cancel: CancelHook,
        block_cancellation: bool = False,
        **kwargs: Mapping[str, int],
    ):
        """Make an absolute move. Keyword arguments should be axis names."""
        raise NotImplementedError("StageStub should not be used directly")

    @thing_action
    def set_zero_position(self):
        """Make the current position zero in all axes

        This action does not move the stage, but resets the position to zero.
        It is intended for use after manually or automatically recentring the
        stage.
        """
        raise NotImplementedError("StageStub should not be used directly")


StageDependency: TypeAlias = direct_thing_client_dependency(StageStub, "/stage/")
