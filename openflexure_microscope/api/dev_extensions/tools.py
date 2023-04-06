import logging
import time

from labthings import fields
from labthings.extensions import BaseExtension
from labthings.views import ActionView


class DevToolsExtension(BaseExtension):
    def __init__(self) -> None:
        super().__init__(
            "org.openflexure.dev.tools",
            version="0.1.0",
            description="Actions to cause various traumatic events in the microscope, used for testing.",
        )
        self.add_view(RaiseException, "/raise")
        self.add_view(SleepFor, "/sleep")


class RaiseException(ActionView):
    def post(self):
        raise Exception("The developer raised an exception")


class SleepFor(ActionView):
    schema = {"TimeAsleep": fields.Float()}
    args = {
        "time": fields.Float(
            metadata={"description": "Time to sleep, in seconds", "example": 0.5}
        )
    }

    def post(self, args):
        sleep_time: int = args.get("time", 0)
        logging.info("Going to sleep for %s...", sleep_time)
        start = time.time()
        time.sleep(sleep_time)
        end = time.time()
        logging.info("Waking up!")
        return {"TimeAsleep": (end - start)}
