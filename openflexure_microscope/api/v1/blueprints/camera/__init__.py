from openflexure_microscope.api.v1.views import MicroscopeView

from flask import Blueprint

from . import capture, record, preview, function


def construct_blueprint(microscope_obj):

    blueprint = Blueprint("camera_blueprint", __name__)

    # Metadata routes
    blueprint.add_url_rule(
        "/capture/<capture_id>/metadata/<filename>",
        view_func=capture.MetadataAPI.as_view(
            "metadata_download", microscope=microscope_obj
        ),
    )

    blueprint.add_url_rule(
        "/capture/<capture_id>/metadata",
        view_func=capture.MetadataRedirectAPI.as_view(
            "metadata_download_redirect", microscope=microscope_obj
        ),
    )

    # Tag routes
    blueprint.add_url_rule(
        "/capture/<capture_id>/tags",
        view_func=capture.TagsAPI.as_view("capture_tags", microscope=microscope_obj),
    )

    # Capture routes
    blueprint.add_url_rule(
        "/capture/<capture_id>/download/<filename>",
        view_func=capture.DownloadAPI.as_view(
            "capture_download", microscope=microscope_obj
        ),
    )

    blueprint.add_url_rule(
        "/capture/<capture_id>/download",
        view_func=capture.DownloadRedirectAPI.as_view(
            "capture_download_redirect", microscope=microscope_obj
        ),
    )

    blueprint.add_url_rule(
        "/capture/<capture_id>/",
        view_func=capture.CaptureAPI.as_view("capture", microscope=microscope_obj),
    )

    blueprint.add_url_rule(
        "/capture/",
        view_func=capture.ListAPI.as_view("capture_list", microscope=microscope_obj),
    )

    # Preview routes
    blueprint.add_url_rule(
        "/preview/<string:operation>",
        view_func=preview.GPUPreviewAPI.as_view(
            "gpu_preview", microscope=microscope_obj
        ),
    )

    # Function routes
    blueprint.add_url_rule(
        "/overlay",
        view_func=function.OverlayAPI.as_view("overlay", microscope=microscope_obj),
    )

    blueprint.add_url_rule(
        "/zoom", view_func=function.ZoomAPI.as_view("zoom", microscope=microscope_obj)
    )

    return blueprint
