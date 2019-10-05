import random
import time
import os
import json
from openflexure_microscope.devel import MicroscopePlugin

from .api import DoAPI, TaskAPI

HERE = os.path.dirname(os.path.realpath(__file__))
FORM_PATH = os.path.join(HERE, "forms.json")


class ExamplePlugin(MicroscopePlugin):
    """
    An example plugin using a comprehensive form
    """

    global FORM_PATH

    with open(FORM_PATH, "r") as sc:
        api_form = json.load(sc)

    api_views = {"/do": DoAPI, "/task": TaskAPI}

    def __init__(self):
        self.val_int = 10
        self.val_str = "Hello"
        self.val_radio = "First"
        self.val_check = ["Foo", "Bar"]
        self.val_select = "Most"
        self.val_unused = "I'm an unused string, here to confuse the form parsing"

        self.run_time = 5

    def set_values(
        self, val_int, val_str, val_radio, val_check, val_select, val_disposable
    ):
        """
        Demonstrate a plugin with form
        """
        if val_int:
            self.val_int = int(val_int)
        if val_str:
            self.val_str = str(val_str)
        if val_radio:
            self.val_radio = val_radio
        if val_check is not None:
            print(val_check)
            self.val_check = val_check if (type(val_check) is list) else [val_check]
        if val_select:
            self.val_select = val_select

        if val_disposable:
            print("DISPOSABLE VALUE: {}".format(val_disposable))

    def get_values_dict(self):
        return {
            "val_int": self.val_int,
            "val_str": self.val_str,
            "val_radio": self.val_radio,
            "val_check": self.val_check,
            "val_select": self.val_select,
            "val_unused": self.val_unused,
        }

    def generate_random_numbers_for_a_while(self, run_time: int):
        self.run_time = run_time
        vals = []
        for _ in range(run_time):
            vals.append(random.random())
            time.sleep(1)

        return vals
