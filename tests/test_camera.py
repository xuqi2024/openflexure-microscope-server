from openflexure_microscope_server.things.camera import CameraProtocol, CameraStub
from openflexure_microscope_server.things.camera.opencv import OpenCVCamera
from openflexure_microscope_server.things.camera.simulation import SimulatedCamera


def test_camera_types():
    assert isinstance(CameraStub(), CameraProtocol)
    assert isinstance(OpenCVCamera(), CameraProtocol)
    assert isinstance(SimulatedCamera(), CameraProtocol)
