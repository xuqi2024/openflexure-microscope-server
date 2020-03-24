from openflexure_microscope.devel import (
    JsonResponse,
    request,
    jsonify,
    taskify,
    update_task_progress,
)

from flask import send_file, abort, url_for

import uuid
import os
import zipfile
import tempfile
import logging

from labthings.server.find import find_component
from labthings.server.view import View
from labthings.server.schema import Schema
from labthings.server import fields
from labthings.server.extensions import BaseExtension
from labthings.server.utilities import description_from_view
from labthings.server.decorators import (
    ThingAction,
    ThingProperty,
    marshal_task,
    marshal_with,
    pre_dump,
)


class ZipObjectSchema(Schema):
    id = fields.String()
    data_size = fields.Number()
    zip_size = fields.Number()
    links = fields.Dict()

    @pre_dump
    def generate_links(self, data, **kwargs):
        data.links = {
            "download": {
                "href": url_for(
                    ZipGetterAPIView.endpoint, session_id=data.id, _external=True
                ),
                **description_from_view(ZipGetterAPIView),
            }
        }
        return data


class ZipObjectDescription:
    def __init__(self, id, file_pointer, data_size=None):
        self.id = id
        self.fp = file_pointer
        self.data_size = data_size
        self.zip_size = os.path.getsize(self.fp.name) * 1e-6

    def close(self):
        logging.debug(self.fp.name)
        self.fp.close()
        os.unlink(self.fp.name)

        assert not os.path.exists(self.fp.name)

    def __del__(self):
        self.close()


class ZipManager:
    """
    ZIP-builder manager
    """

    def __init__(self):
        super().__init__()

        self.session_zips = {}

    def build_zip_from_capture_ids(self, microscope, capture_id_list):
        logging.debug(capture_id_list)

        # Get array of captures from IDs
        capture_list = [
            microscope.camera.images.get(capture_id) for capture_id in capture_id_list
        ]
        # Remove Nones from list (missing/invalid captures)
        capture_list = [capture for capture in capture_list if capture]

        # Get size (in bytes) of each capture
        capture_sizes = [
            os.path.getsize(capture_obj.file) for capture_obj in capture_list
        ]
        # Calculate size of input data in megabytes
        data_size_megabytes = sum(capture_sizes) * 1e-6

        # If more than 1GB
        if data_size_megabytes > 1000:
            # Throw exception
            raise Exception(
                "Zip data cannot exceed 1GB. Please transfer data manually."
            )

        # Number of files to add (used for task progress)
        n_files = len(capture_id_list)

        # Create temporary file
        fp = tempfile.NamedTemporaryFile(delete=False)

        # Open temp file as a ZIP file
        with zipfile.ZipFile(fp, "w") as zipObj:
            for index, capture_obj in enumerate(capture_list):
                # Add to ZIP file if it exists
                file_path = capture_obj.file
                rel_path = os.path.relpath(
                    file_path, microscope.camera.paths["default"]
                )
                zipObj.write(file_path, arcname=rel_path)
                # Update task progress
                update_task_progress(int((index / n_files) * 100))

        session_id = str(uuid.uuid4())
        session_description = ZipObjectDescription(
            session_id, fp, data_size=data_size_megabytes
        )
        self.session_zips[session_id] = session_description

        return self.session_zips[session_id]

    def marshaled_build_zip_from_capture_ids(self, *args, **kwargs):
        return ZipObjectSchema().dump(self.build_zip_from_capture_ids(*args, **kwargs))

    def zip_fp_from_id(self, session_id):
        return self.session_zips[session_id].fp

    def __del__(self):
        for zd in self.session_zips.values():
            zd.close()


# Create a global ZIP manager
default_zip_manager = ZipManager()


@ThingAction
class ZipBuilderAPIView(View):
    @marshal_task
    def post(self):

        ids = list(JsonResponse(request).json)
        microscope = find_component("org.openflexure.microscope")

        task = taskify(default_zip_manager.marshaled_build_zip_from_capture_ids)(
            microscope, ids
        )

        # Return a handle on the autofocus task
        return task


@ThingProperty
class ZipListAPIView(View):
    @marshal_with(ZipObjectSchema(many=True))
    def get(self):
        return default_zip_manager.session_zips.values()


class ZipGetterAPIView(View):
    """
    Download or delete a particular capture collection ZIP file
    """

    def get(self, session_id):
        """
        Download a particular capture collection ZIP file
        """
        if not session_id in default_zip_manager.session_zips:
            return abort(404)  # 404 Not Found

        logging.info(f"Session ID: {session_id}")

        return send_file(
            default_zip_manager.zip_fp_from_id(session_id).name,
            mimetype="application/zip",
            as_attachment=True,
            attachment_filename=f"{session_id}.zip",
        )

    def delete(self, session_id):
        """
        Close and delete a particular capture collection ZIP file
        """
        if not session_id in default_zip_manager.session_zips:
            return abort(404)  # 404 Not Found

        # Close the file
        default_zip_manager.session_zips[session_id].close()
        # Delete the file reference
        del default_zip_manager.session_zips[session_id]

        return {"return": session_id}


zip_extension_v2 = BaseExtension(
    "org.openflexure.zipbuilder",
    version="2.0.0",
    description="Build and download capture collections as ZIP files",
)

zip_extension_v2.add_view(ZipGetterAPIView, "/get/<string:session_id>")
zip_extension_v2.add_view(ZipListAPIView, "/get")

zip_extension_v2.add_view(ZipBuilderAPIView, "/build")
