import datetime
import io
import os
import uuid
from collections import OrderedDict

import piexif
from PIL import Image, ImageChops

from openflexure_microscope.captures import THUMBNAIL_SIZE, CaptureObject
from openflexure_microscope.captures.capture import (
    build_captures_from_exif,
    capture_from_path,
)

IN_DIR = "tests/images/"
OUT_DIR = "tests/images/out/"


def generate_small_image():
    # Create a dummy image to serve in the stream
    image = Image.new("RGB", (20, 20), color=(0, 0, 0))

    return image


def generate_small_thumbnail():
    # Create a dummy image to serve in the stream
    image = Image.new("RGB", (20, 20), color=(0, 0, 0))
    image.thumbnail(THUMBNAIL_SIZE)

    return image


def generate_small_capture(filename: str):
    out = os.path.join(OUT_DIR, filename)
    obj = CaptureObject(out)
    generate_small_image().save(obj, format="JPEG")

    return obj


def check_valid_capture(obj: CaptureObject):
    assert isinstance(obj.time, datetime.datetime)
    assert isinstance(obj.id, uuid.UUID)

    assert isinstance(obj.annotations, dict)
    assert isinstance(obj.tags, list)

    assert obj.file
    assert obj.format
    assert obj.basename
    assert obj.filefolder
    assert obj.name


def check_valid_openflexure_metadata(d: dict):
    assert "image" in d
    assert d["image"].get("id")
    assert d["image"].get("name")
    assert d["image"].get("time")
    assert d["image"].get("format")

    assert isinstance(d["image"].get("tags"), list)
    assert isinstance(d["image"].get("annotations"), dict)


def test_new_capture_object():
    obj = generate_small_capture("capture0.jpg")
    check_valid_capture(obj)


def test_initial_metadata():
    obj = generate_small_capture("capture1.jpg")

    data = obj.read_full_metadata()
    check_valid_openflexure_metadata(data)


def test_tags():
    obj = generate_small_capture("capture2.jpg")

    obj.put_tags(["foo", "bar"])
    assert obj.read_full_metadata()["image"]["tags"] == ["foo", "bar"]

    obj.delete_tag("foo")
    assert obj.read_full_metadata()["image"]["tags"] == ["bar"]

    # Delete nonexistent tag, should change nothing
    obj.delete_tag("foo")
    assert obj.read_full_metadata()["image"]["tags"] == ["bar"]


def test_annotations():
    obj = generate_small_capture("capture3.jpg")

    obj.put_annotations({"foo": "zoo", "bar": "zar"})
    assert obj.read_full_metadata()["image"]["annotations"] == {
        "foo": "zoo",
        "bar": "zar",
    }

    obj.delete_annotation("foo")
    assert obj.read_full_metadata()["image"]["annotations"] == {"bar": "zar"}

    # Delete nonexistent annotation, should change nothing
    obj.delete_annotation("foo")
    assert obj.read_full_metadata()["image"]["annotations"] == {"bar": "zar"}


def test_put_metadata():
    obj = generate_small_capture("capture4.jpg")

    obj.put_metadata({"foo": {"bar": "zar"}})
    assert obj.read_full_metadata()["foo"] == {"bar": "zar"}


def test_put_and_save():
    obj = generate_small_capture("capture_all.jpg")
    obj.put_and_save(
        tags=["foo", "bar"],
        annotations={"foo": "zoo", "bar": "zar"},
        metadata={"foo": {"bar": "zar"}},
    )

    full_metadata = obj.read_full_metadata()
    assert full_metadata["image"]["tags"] == ["foo", "bar"]
    assert full_metadata["image"]["annotations"] == {"foo": "zoo", "bar": "zar"}
    assert full_metadata["foo"] == {"bar": "zar"}


def test_capture_from_path_this_version():
    """Tests reloading a capture object from a file created in the working server version"""

    def _check_metadata(data: dict):
        assert data["image"]["tags"] == ["foo", "bar"]
        assert data["image"]["annotations"] == {"foo": "zoo", "bar": "zar"}
        assert data["foo"] == {"bar": "zar"}

    # Create the capture file
    obj_in = generate_small_capture("capture_reload.jpg")
    obj_in.put_and_save(
        tags=["foo", "bar"],
        annotations={"foo": "zoo", "bar": "zar"},
        metadata={"foo": {"bar": "zar"}},
    )

    full_metadata_in = obj_in.read_full_metadata()
    check_valid_openflexure_metadata(full_metadata_in)
    _check_metadata(full_metadata_in)

    # Reload the capture file
    obj = capture_from_path(os.path.join(OUT_DIR, "capture_reload.jpg"))
    check_valid_capture(obj)
    full_metadata = obj.read_full_metadata()
    check_valid_openflexure_metadata(full_metadata)
    _check_metadata(full_metadata)


def test_capture_from_path_v280():
    """Tests reloading a capture object from a file created in server v2.8.0"""
    obj = capture_from_path(os.path.join(IN_DIR, "capture_v280.jpg"))
    check_valid_capture(obj)
    full_metadata = obj.read_full_metadata()
    check_valid_openflexure_metadata(full_metadata)
    assert full_metadata["image"]["tags"] == ["foo", "bar"]
    assert full_metadata["image"]["annotations"] == {"foo": "zoo", "bar": "zar"}
    assert full_metadata["foo"] == {"bar": "zar"}


def test_build_captures_from_exif():
    # Load the whole tests captures directory
    objs = build_captures_from_exif(IN_DIR)
    # Make sure we have a valid, populated OrderedDict
    assert isinstance(objs, OrderedDict)
    assert len(objs) > 0
    # Check each reloaded capture
    for obj in objs.values():
        check_valid_capture(obj)


def test_data():
    # Get a reference PIL image
    ref_data = generate_small_image()
    # Generate a capture with the same image data as our reference
    obj = generate_small_capture("capture5.jpg")
    # Pull the capture data out
    obj_data = Image.open(obj.data)
    # Compare the images
    diff = ImageChops.difference(obj_data, ref_data)
    assert not diff.getbbox()


def test_binary():
    # Get a reference PIL image
    ref_data = generate_small_image()
    # Generate a capture with the same image data as our reference
    obj = generate_small_capture("capture6.jpg")
    # Pull the capture data out
    obj_data = Image.open(io.BytesIO(obj.binary))
    # Compare the images
    diff = ImageChops.difference(obj_data, ref_data)
    assert not diff.getbbox()


def test_thumbnail():
    # Get a reference PIL image
    ref_thumb = generate_small_thumbnail()
    # Generate a capture with the same image data as our reference
    obj = generate_small_capture("capture7.jpg")
    # Pull the generated thumbnail out
    obj_thumb = Image.open(obj.thumbnail)
    # Compare the images
    diff = ImageChops.difference(obj_thumb, ref_thumb)
    assert not diff.getbbox()

    # Assert thumbnail was saved to capture file EXIF data
    exif_dict = piexif.load(obj.file)
    thumbnail = exif_dict.pop("thumbnail")
    assert thumbnail
    # Compare the images
    diff = ImageChops.difference(Image.open(io.BytesIO(thumbnail)), ref_thumb)


def test_delete():
    # Generate a capture with the same image data as our reference
    obj = generate_small_capture("capture_del.jpg")
    assert os.path.isfile(obj.file)
    obj.delete()
    assert not os.path.isfile(obj.file)
