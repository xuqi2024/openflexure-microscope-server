from openflexure_microscope.api.app import api_microscope, app, labthing
from openflexure_microscope.camera.base import BaseCamera
from openflexure_microscope.microscope import Microscope
from openflexure_microscope.stage.base import BaseStage


def test_app_creation():
    assert labthing.app is app


def test_microscope_creation():
    assert isinstance(api_microscope, Microscope)
    assert isinstance(api_microscope.camera, BaseCamera)
    assert isinstance(api_microscope.stage, BaseStage)
