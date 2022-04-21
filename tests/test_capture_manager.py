import os
from typing import Type

import pytest
from freezegun import freeze_time

from openflexure_microscope.captures.capture_manager import (
    BASE_CAPTURE_PATH,
    TEMP_CAPTURE_PATH,
    CaptureManager,
)


def test_new_manager():
    m = CaptureManager()
    assert m.paths["default"]
    assert m.paths["temp"]


def test_update_settings():
    m = CaptureManager()
    assert m.paths["default"] != "BASE_CAPTURE_PATH"
    assert m.paths["temp"] != "TEMP_CAPTURE_PATH"

    new_settings = {
        "paths": {"default": "BASE_CAPTURE_PATH", "temp": "TEMP_CAPTURE_PATH"}
    }
    m.update_settings(new_settings)
    assert m.paths["default"] == "BASE_CAPTURE_PATH"
    assert m.paths["temp"] == "TEMP_CAPTURE_PATH"
    assert m.read_settings() == new_settings


def test__new_output():
    m = CaptureManager()

    out = m._new_output(True, "filename", "subfolder", "fmt")
    assert out.file == os.path.join(TEMP_CAPTURE_PATH, "subfolder", "filename.fmt")


def test__new_output_generate_filename():
    m = CaptureManager()

    out = m._new_output(True, None, "subfolder", "fmt")
    # Assert a filename was actually generated
    assert out.name != ".fmt"


def test_new_image():
    m = CaptureManager()
    out = m.new_image()
    capture_key = str(out.id)
    assert capture_key in m.images.keys()
    assert m.images[capture_key] is out


def test_new_video():
    m = CaptureManager()
    out = m.new_video()
    capture_key = str(out.id)
    assert capture_key in m.videos.keys()
    assert m.videos[capture_key] is out


def test_image_from_id_str():
    m = CaptureManager()
    out = m.new_image()
    capture_key = str(out.id)

    assert m.image_from_id(capture_key) is out


def test_image_from_id_int():
    m = CaptureManager()
    out = m.new_image()
    capture_key = int(out.id)

    assert m.image_from_id(capture_key) is out


def test_image_from_id_uuid():
    m = CaptureManager()
    out = m.new_image()
    capture_key = out.id

    assert m.image_from_id(capture_key) is out


def test_image_from_id_invalid():
    m = CaptureManager()
    out = m.new_image()
    capture_key = object()

    with pytest.raises(TypeError):
        m.image_from_id(capture_key) is out


def test_video_from_id_str():
    m = CaptureManager()
    out = m.new_video()
    capture_key = str(out.id)

    assert m.video_from_id(capture_key) is out


def test_video_from_id_int():
    m = CaptureManager()
    out = m.new_video()
    capture_key = int(out.id)

    assert m.video_from_id(capture_key) is out


def test_video_from_id_uuid():
    m = CaptureManager()
    out = m.new_video()
    capture_key = out.id

    assert m.video_from_id(capture_key) is out


def test_video_from_id_invalid():
    m = CaptureManager()
    out = m.new_video()
    capture_key = object()

    with pytest.raises(TypeError):
        m.video_from_id(capture_key) is out


@freeze_time("2020-11-27 12:00:01")
def test_generate_numbered_basename():
    m = CaptureManager()
    for _ in range(10):
        m.new_image()
    generated_filenames = [obj.basename for obj in m.images.values()]
    # Assert enough names were generated
    assert len(generated_filenames) == 10
    # Assert all names are unique
    len(generated_filenames) > len(set(generated_filenames))
    # Assert all filenames are in the expected form
    for fname in generated_filenames:
        assert fname.startswith("2020-11-27_12-00-01")


def test_context_manager():
    with CaptureManager() as m:
        m.new_image()
        m.new_video()
