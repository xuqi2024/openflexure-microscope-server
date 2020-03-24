"""
Top-level representation of enabled actions
"""
from flask import url_for
from . import camera, stage, system

from labthings.server.view import View
from labthings.server.find import current_labthing
from labthings.server.utilities import description_from_view
from labthings.server.decorators import Tag

_actions = {
    "capture": {
        "rule": "/camera/capture/",
        "view_class": camera.CaptureAPI,
        "conditions": True,
    },
    "ramCapture": {
        "rule": "/camera/ram-capture/",
        "view_class": camera.RAMCaptureAPI,
        "conditions": True,
    },
    "previewStart": {
        "rule": "/camera/preview/start",
        "view_class": camera.GPUPreviewStartAPI,
        "conditions": True,
    },
    "previewStop": {
        "rule": "/camera/preview/stop",
        "view_class": camera.GPUPreviewStopAPI,
        "conditions": True,
    },
    "move": {
        "rule": "/stage/move/",
        "view_class": stage.MoveStageAPI,
        "conditions": True,
    },
    "zeroStage": {
        "rule": "/stage/zero/",
        "view_class": stage.ZeroStageAPI,
        "conditions": True,
    },
    "shutdown": {
        "rule": "/system/shutdown/",
        "view_class": system.ShutdownAPI,
        "conditions": system.is_raspberrypi(),
    },
    "reboot": {
        "rule": "/system/reboot/",
        "view_class": system.RebootAPI,
        "conditions": system.is_raspberrypi(),
    },
}


def enabled_root_actions():
    global _actions
    return {k: v for k, v in _actions.items() if v["conditions"]}


@Tag("actions")
class ActionsView(View):
    def get(self):
        """
        List of enabled default API actions.

        This list does not include any actions added by LabThings extensions, only
        those part of the default OpenFlexure Microscope API.
        """
        global _actions

        actions = {}
        for name, action in enabled_root_actions().items():
            d = {
                "links": {
                    "self": {
                        "href": url_for(action["view_class"].endpoint, _external=True),
                        "mimetype": "application/json",
                        **description_from_view(action["view_class"]),
                    }
                },
                "rule": action["rule"],
                "view_class": str(action["view_class"]),
            }

            actions[name] = d

        return actions
