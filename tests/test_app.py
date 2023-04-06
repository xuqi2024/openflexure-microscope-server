from apispec.utils import validate_spec
import json
import jsonschema
import os

from openflexure_microscope.api.app import api_microscope, app, labthing
from openflexure_microscope.camera.base import BaseCamera
from openflexure_microscope.microscope import Microscope
from openflexure_microscope.stage.base import BaseStage
from labthings.json import encode_json


def test_app_creation():
    assert labthing.app is app


def test_microscope_creation():
    assert isinstance(api_microscope, Microscope)
    assert isinstance(api_microscope.camera, BaseCamera)
    assert isinstance(api_microscope.stage, BaseStage)


def test_openapi_valid():
    assert validate_spec(labthing.spec)


def test_thing_description_valid():
    # TODO: it would be nice to put this into LabThings
    # First load the schema from file and check it validates
    schema_fname = os.path.join(os.path.dirname(__file__), "w3c_td_schema.json")
    schema = json.load(open(schema_fname, "r"), encoding="utf-8")
    jsonschema.Draft7Validator.check_schema(schema)

    # Build a TD dictionary
    with labthing.app.test_request_context():
        td_dict = labthing.thing_description.to_dict()

    # Allow our LabThingsJSONEncoder to encode the RD
    td_json = encode_json(td_dict)
    # Decode the JSON back into a primitive dictionary
    td_json_dict = json.loads(td_json)
    # Validate
    jsonschema.validate(instance=td_json_dict, schema=schema)
