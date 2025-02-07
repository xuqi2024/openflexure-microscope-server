"""
OpenFlexure Microscope API test Thing

This Thing is intended only for use testing out the API and client(s).
"""

from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_fastapi.dependencies.invocation import CancelHook, InvocationLogger


class APITestThing(Thing):
    _counter: int = 0

    @thing_property
    def counter(self) -> int:
        return self._counter

    @thing_action
    def count_slowly(
        self,
        cancel: CancelHook,
        logger: InvocationLogger,
        n=100,
        dt=0.1,
    ) -> None:
        for i in range(n):
            self._counter = i
            print(f"counted to {i}")
            logger.info(f"Counted to {i}")
            cancel.sleep(dt)
        self._counter = n
