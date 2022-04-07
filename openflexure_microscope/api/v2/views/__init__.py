from .actions import enabled_root_actions
from .camera import *
from .captures import *
from .instrument import *
from .stage import *
from .streams import *
from openflexure_microscope.api.logging_configuration import LogFileView

def add_views_to_labthing(labthing):
    # Attach captures resources
    labthing.add_view(CaptureList, "/captures")
    labthing.add_root_link(CaptureList, "captures")

    labthing.add_view(CaptureView, "/captures/<id_>")
    labthing.add_view(CaptureDownload, "/captures/<id_>/download/<filename>")
    labthing.add_view(CaptureTags, "/captures/<id_>/tags")
    labthing.add_view(CaptureAnnotations, "/captures/<id_>/annotations")

    # Attach settings and state resources
    labthing.add_view(SettingsProperty, "/instrument/settings")
    labthing.add_root_link(SettingsProperty, "instrumentSettings")
    labthing.add_view(NestedSettingsProperty, "/instrument/settings/<path:route>")
    labthing.add_view(StateProperty, "/instrument/state")
    labthing.add_view(NestedStateProperty, "/instrument/state/<path:route>")
    labthing.add_root_link(StateProperty, "instrumentState")
    labthing.add_view(ConfigurationProperty, "/instrument/configuration")
    labthing.add_view(
        NestedConfigurationProperty, "/instrument/configuration/<path:route>"
    )
    labthing.add_root_link(ConfigurationProperty, "instrumentConfiguration")

    # Attach stage resources
    labthing.add_view(StageTypeProperty, "/instrument/stage/type")

    # Attach camera resources
    labthing.add_view(LSTImageProperty, "/instrument/camera/lst")

    # Attach streams resources
    labthing.add_view(MjpegStream, "/streams/mjpeg")
    labthing.add_view(SnapshotStream, "/streams/snapshot")

    # Attach microscope action resources
    for name, action in enabled_root_actions().items():
        view_class = action["view_class"]
        rule = action["rule"]
        labthing.add_view(view_class, f"/actions{rule}")

    labthing.add_view(LogFileView, "/log")