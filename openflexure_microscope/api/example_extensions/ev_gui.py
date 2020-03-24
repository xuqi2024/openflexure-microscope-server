from labthings.server.view import View
from labthings.server.extensions import BaseExtension
from labthings.server.decorators import ThingAction, ThingProperty

from openflexure_microscope.api.utilities.gui import build_gui

import logging

from flask import jsonify

# Some value that will change over time
# Here, we add 1 to it every time a GET request is made
val_int = 0


def dynamic_form():
    global val_int
    return {
        "id": "test-plugin",
        "icon": "pets",
        "forms": [
            {
                "name": "Simple request",
                "isCollapsible": False,
                "isTask": False,
                "selfUpdate": True,
                "route": "/do",
                "submitLabel": "Do things",
                "schema": [
                    {
                        "fieldType": "numberInput",
                        "name": "val_int",
                        "label": "Number value",
                        "minValue": 0,
                        "value": val_int,
                    },
                    {
                        "fieldType": "htmlBlock",
                        "name": "html_block",
                        "content": f"<i>Value is: </i><br>{val_int}.",  # We dynamically use the val_int variable
                    },
                ],
            }
        ],
    }


# Alternate form without any dynamic parts
static_form = {
    "id": "test-plugin",
    "icon": "pets",
    "forms": [
        {
            "name": "Simple request",
            "isCollapsible": False,
            "isTask": False,
            "selfUpdate": True,
            "route": "/do",
            "submitLabel": "Do things",
            "schema": [
                {
                    "fieldType": "numberInput",
                    "name": "val_int",
                    "label": "Number value",
                    "minValue": 0,
                    "default": 1,
                },
                {
                    "fieldType": "htmlBlock",
                    "name": "html_block",
                    "content": f"<i>Value is fixed</i>.",
                },
            ],
        }
    ],
}


@ThingProperty
class TestAPIView(View):
    def get(self):
        global val_int
        val_int += 1
        return jsonify({"val": True})


@ThingAction
class TestDoAPIView(View):
    def post(self):
        global val_int
        val_int += 1
        return jsonify({"val": True})


# Using the dynamic form
dynamic_test_extension_v2 = BaseExtension("org.openflexure.examples.dynamic-gui")
dynamic_test_extension_v2.add_view(
    TestAPIView, "/get", endpoint="dynamic_test_extension_get"
)
dynamic_test_extension_v2.add_view(
    TestDoAPIView, "/do", endpoint="dynamic_test_extension_do"
)

dynamic_test_extension_v2.add_meta(
    "gui", build_gui(dynamic_form, dynamic_test_extension_v2)
)


# Using the static form
static_test_extension_v2 = BaseExtension("org.openflexure.examples.static-gui")
static_test_extension_v2.add_view(
    TestAPIView, "/get", endpoint="static_test_extension_get"
)
static_test_extension_v2.add_view(
    TestDoAPIView, "/do", endpoint="static_test_extension_do"
)
static_test_extension_v2.add_meta(
    "gui", build_gui(static_form, static_test_extension_v2)
)
