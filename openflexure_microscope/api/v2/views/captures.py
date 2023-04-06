from io import BytesIO
from typing import List, Optional, Union
from uuid import UUID

from flask import abort, redirect, request, send_file, url_for
from labthings import Schema, fields, find_component
from labthings.marshalling import marshal_with, use_args
from labthings.utilities import description_from_view
from labthings.views import PropertyView, View
from marshmallow import pre_dump

from openflexure_microscope.api.utilities import get_bool
from openflexure_microscope.captures import CaptureObject

# SCHEMAS


class InstrumentSchema(Schema):
    id = fields.UUID()
    configuration = fields.Dict()
    settings = fields.Dict()
    state = fields.Dict()


class ImageSchema(Schema):
    id = fields.UUID()
    time = fields.String(metadata={"format": "date"})
    format = fields.String()
    name = fields.String()
    tags = fields.List(fields.String())
    annotations = fields.Dict(keys=fields.Str(), values=fields.Str())


class CaptureMetadataSchema(Schema):
    # Full dataset dictionary will change depending on the type of
    # dataset, so we can't make a specific schema in this case.
    dataset = fields.Dict()
    # Nested schema for Image data
    image = fields.Nested(ImageSchema())
    # Nested schema for instrument data
    instrument = fields.Nested(InstrumentSchema())


class BasicDatasetSchema(Schema):
    id = fields.UUID()
    name = fields.String()
    type = fields.String()


class CaptureSchema(ImageSchema):
    """
    Schema containing only basic attributes required
    for interacting with a capture. Additional attributes
    are returned by using FullCaptureSchema 
    """

    # We need dataset information in the capture array
    # so that client applications can sort data into folders
    # without the server having to do a tonne of file IO
    dataset = fields.Nested(BasicDatasetSchema())
    file = fields.String(
        data_key="path", metadata={"description": "Path of file on microscope device"}
    )
    # No need to make a schema for links as we only ever
    # create the dictionary right here in `generate_links`
    links = fields.Dict()

    @pre_dump
    def generate_links(self, data: Union[dict, CaptureObject], **_):
        if isinstance(data, dict):
            capture_id: Optional[Union[str, UUID]] = data.get("id")
            capture_name: Optional[str] = data.get("name")
        else:
            capture_id = data.id
            capture_name = data.name

        links = {
            "self": {
                "href": url_for(CaptureView.endpoint, id_=capture_id, _external=True),
                "mimetype": "application/json",
                **description_from_view(CaptureView),
            }
            if CaptureView.endpoint
            else {},
            "tags": {
                "href": url_for(CaptureTags.endpoint, id_=capture_id, _external=True),
                "mimetype": "application/json",
                **description_from_view(CaptureTags),
            }
            if CaptureTags.endpoint
            else {},
            "annotations": {
                "href": url_for(
                    CaptureAnnotations.endpoint, id_=capture_id, _external=True
                ),
                "mimetype": "application/json",
                **description_from_view(CaptureAnnotations),
            }
            if CaptureAnnotations.endpoint
            else {},
            "download": {
                "href": url_for(
                    CaptureDownload.endpoint,
                    id_=capture_id,
                    filename=capture_name,
                    _external=True,
                ),
                "mimetype": "image/jpeg",
                **description_from_view(CaptureDownload),
            }
            if CaptureDownload.endpoint
            else {},
        }

        if isinstance(data, dict):
            data["links"] = links
        else:
            setattr(data, "links", links)

        return data


class FullCaptureSchema(CaptureSchema):
    """
    Capture schema including metadata. We exclude this by default
    since it can become huge due to complex settings including
    lens shading tables and CSM matrices.
    """

    metadata = fields.Nested(CaptureMetadataSchema())


# VIEWS


class CaptureList(PropertyView):
    tags = ["captures"]
    schema = CaptureSchema(many=True)

    def get(self):
        """
        List all image captures
        """
        microscope = find_component("org.openflexure.microscope")
        image_list: List[CaptureObject] = microscope.captures.images.values()
        return image_list


CAPTURE_ID_PARAMETER = {
    "name": "id_",
    "in": "path",
    "description": "The unique ID of the capture",
    "required": True,
    "schema": {"type": "string"},
    "example": "eeae7ae9-0c0d-45a4-9ef2-7b84bb67a1d1",
}


class CaptureView(View):
    tags = ["captures"]
    parameters = [CAPTURE_ID_PARAMETER]

    @marshal_with(FullCaptureSchema())
    def get(self, id_):
        """
        Description of a single image capture
        """
        microscope = find_component("org.openflexure.microscope")
        capture_obj: Optional[CaptureObject] = microscope.captures.images.get(id_)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        return capture_obj

    get.responses = {404: {"description": "Capture object was not found"}}

    def delete(self, id_):
        """
        Delete a single image capture
        """
        microscope = find_component("org.openflexure.microscope")
        capture_obj: Optional[CaptureObject] = microscope.captures.images.get(id_)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        # Delete the capture file
        capture_obj.delete()
        # Delete from capture list
        del microscope.captures.images[id_]

        return "", 204


class CaptureDownload(View):
    tags = ["captures"]
    responses = {
        200: {"content": {"image/jpeg": {}}, "description": "Image data in JPEG format"}
    }
    parameters = [
        CAPTURE_ID_PARAMETER,
        {
            "name": "filename",
            "in": "path",
            "description": "The filename of the downloaded image.",
            "required": False,
            "schema": {"type": "string"},
            "example": "myimage.jpeg",
        },
    ]

    def get(self, id_, filename: Optional[str]):
        """
        Image data for a single image capture
        """
        microscope = find_component("org.openflexure.microscope")
        capture_obj: Optional[CaptureObject] = microscope.captures.images.get(id_)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        thumbnail: bool = get_bool(request.args.get("thumbnail", ""))

        # If no filename is specified, redirect to the capture's currently set filename
        if not filename:
            return redirect(
                url_for(
                    "DownloadAPI",
                    id=id_,
                    filename=capture_obj.name,
                    thumbnail=thumbnail,
                ),
                code=307,
            )

        # Download the image data using the requested filename
        if thumbnail:
            img: Optional[BytesIO] = capture_obj.thumbnail
        else:
            img = capture_obj.data

        # If we can't get any data, return 404
        if not img:
            return abort(404)  # 404 Not Found

        return send_file(img, mimetype="image/jpeg")


class CaptureTags(View):
    tags = ["captures"]
    parameters = [CAPTURE_ID_PARAMETER]

    def get(self, id_):
        """
        Get tags associated with a single image capture
        """
        microscope = find_component("org.openflexure.microscope")
        capture_obj: Optional[CaptureObject] = microscope.captures.images.get(id_)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        return capture_obj.tags

    @use_args(fields.List(fields.String(), required=True))
    def put(self, args, id_):
        """
        Add tags to a single image capture
        """
        microscope = find_component("org.openflexure.microscope")
        capture_obj: Optional[CaptureObject] = microscope.captures.images.get(id_)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        capture_obj.put_tags(args)

        return capture_obj.tags

    @use_args(fields.List(fields.String(), required=True))
    def delete(self, args, id_):
        """
        Delete tags from a single image capture
        """
        microscope = find_component("org.openflexure.microscope")
        capture_obj: Optional[CaptureObject] = microscope.captures.images.get(id_)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        for tag in args:
            capture_obj.delete_tag(str(tag))

        return capture_obj.tags


class CaptureAnnotations(View):
    tags = ["captures"]
    parameters = [CAPTURE_ID_PARAMETER]

    def get(self, id_):
        """
        Get annotations associated with a single image capture
        """
        microscope = find_component("org.openflexure.microscope")
        capture_obj: Optional[CaptureObject] = microscope.captures.images.get(id_)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        return capture_obj.annotations

    @use_args(fields.Dict())
    def put(self, args, id_):
        """
        Update metadata for a single image capture
        """
        microscope = find_component("org.openflexure.microscope")
        capture_obj = microscope.captures.images.get(id_)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        capture_obj.put_annotations(args)

        return capture_obj.annotations
