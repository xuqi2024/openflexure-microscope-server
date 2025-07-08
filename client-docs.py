#! /usr/bin/env python3
import unittest.mock as mock
from labthings_fastapi.descriptors.action import ActionDescriptor
from labthings_fastapi.descriptors.property import ThingProperty, ThingSetting
from labthings_fastapi.utilities import attributes

mocky_d = {
    "picamera2": mock.MagicMock(),
    "picamera2.encoders": mock.MagicMock(),
    "picamera2.outputs": mock.MagicMock(),
}

with mock.patch.dict("sys.modules", mocky_d):
    from openflexure_microscope_server.things.camera.picamera import StreamingPiCamera2

    thing_class = StreamingPiCamera2
    for name, item in attributes(thing_class):
        if isinstance(item, ThingProperty):
            if isinstance(item, ThingSetting):
                print(f"Setting: {name}")
            else:
                print(f"Property: {name}")
        elif isinstance(item, ActionDescriptor):
            print(f"\n\nAction: {name}")
            print(item.description)
            if item.input_model.model_fields:
                print("  Inputs")
            if item.output_model:
                print("  outputs")
            if item.dependency_params:
                print("  Dependencies")
            for dep in item.dependency_params:
                print(f"    {dep.annotation.__metadata__[0].dependency.__name__}")
            print("\n\n")
