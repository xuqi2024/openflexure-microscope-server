from labthings.server.extensions import BaseExtension
from labthings.server.view import View
from labthings.server.decorators import ThingProperty, PropertySchema, use_args
from labthings.server import fields
from labthings.server.find import find_component

from openflexure_microscope.paths import settings_file_path, check_rw
from openflexure_microscope.config import OpenflexureSettingsFile
from openflexure_microscope.camera.base import BASE_CAPTURE_PATH
from openflexure_microscope.camera.capture import build_captures_from_exif

from openflexure_microscope.api.utilities.gui import build_gui

from flask import abort
import logging
import os
import psutil

from sys import platform


AS_SETTINGS_PATH = settings_file_path("autostorage_settings.json")


def get_partitions():
    return [disk.mountpoint for disk in psutil.disk_partitions() if "rw" in disk.opts]


def get_permissive_partitions():
    return [partition for partition in get_partitions() if check_rw(partition)]


def get_permissive_locations():
    return [
        (partition, os.path.join(partition, "openflexure", "data", "micrographs"))
        for partition in get_permissive_partitions()
    ]


def get_current_location(camera):
    return camera.paths.get("default")


def set_current_location(camera, location: str):
    if not os.path.isdir(location):
        os.makedirs(location)
    logging.debug("Updating location...")
    camera.paths.update({"default": location})
    logging.debug("Rebuilding captures...")
    camera.rebuild_captures()
    logging.debug("Capture location changed successfully.")


def get_default_location():
    return BASE_CAPTURE_PATH


def get_all_locations():
    locations = {}
    # If default is not already listed (e.g. if it's currently set)
    if get_default_location() not in locations.values():
        locations["Default"] = get_default_location()

    for ppartition, plocation in get_permissive_locations():
        pdrive = os.path.splitdrive(plocation)[0]
        if not (
            pdrive  # If path actually has a drive (basically just Windows?)
            and any(  # And shares a common drive with an existing location
                [
                    pdrive == os.path.splitdrive(location)[0]
                    for location in locations.values()
                ]
            )
        ):
            locations[ppartition] = plocation

    # Strip out Nones
    return {k: v for k, v in locations.items() if v}


class CaptureStorageLocation:
    def __init__(self, mountpoint):
        pass


class AutostorageExtension(BaseExtension):
    def __init__(self):
        BaseExtension.__init__(
            self,
            "org.openflexure.autostorage",
            version="2.0.0",
            description="Handle switching capture storage devices",
        )

        # We'll store a reference to a camera object, who's capture paths will be modified
        self.camera = None

        self.initial_location = get_default_location()

        # Register the on_microscope function to run when the microscope is attached
        self.on_component("org.openflexure.microscope", self.on_microscope)

    def on_microscope(self, microscope_obj):
        """Function to automatically call when the parent LabThing has a microscope attached."""
        logging.debug(f"Autostorage extension found microscope {microscope_obj}")
        if hasattr(microscope_obj, "camera"):
            logging.debug(f"Autostorage extension bound to camera {self.camera}")

            # Store a reference to the camera
            self.camera = microscope_obj.camera
            # Store the initial storage location
            self.initial_location = get_current_location(self.camera)

            # If preferred path does not exist, or cannot be written to
            self.check_location(self.initial_location)

            logging.debug(self.get_locations())

    def check_location(self, location=None):
        if not location:
            location = get_current_location(self.camera)
        # If preferred path does not exist, or cannot be written to
        if not (os.path.isdir(location) and check_rw(location)):
            logging.error(
                f"Preferred capture path {location} is missing or cannot be written to. Restoring defaults."
            )
            # Reset the storage location to default
            set_current_location(self.camera, get_default_location())

    def get_locations(self):
        if self.camera:
            locations = get_all_locations()

            current_location = get_current_location(self.camera)
            if current_location not in locations.values():
                locations.update({"Custom": current_location})
            # Add location from the cameras settings file
            return locations
        else:
            return {}

    def get_preferred_key(self):
        current = get_current_location(self.camera)
        locations = self.get_locations()

        matches = [k for k, v in locations.items() if v == current]

        if len(matches) > 1:
            logging.warning(
                "Multiple path matches found. Weird, but carrying on using zeroth."
            )

        return matches[0]

    def set_preferred_key(self, new_path_key: str):
        if not new_path_key in self.get_locations().keys():
            raise KeyError(f"No location named {new_path_key}")

        location = self.get_locations().get(new_path_key)
        set_current_location(self.camera, location)

    def key_to_title(self, path_key: str):
        if not path_key in self.get_locations().keys():
            raise KeyError(f"No location named {path_key}")

        return f"{path_key} ({self.get_locations().get(path_key)})"

    def title_to_key(self, path_title: str):
        matches = []
        for loc_key in self.get_locations().keys():
            if path_title.startswith(loc_key):
                matches.append(loc_key)

        if len(matches) > 1:
            logging.warning(
                "Multiple path matches found. Weird, but carrying on using zeroth."
            )

        return matches[0]

    def get_titles(self):
        return [self.key_to_title(key) for key in self.get_locations().keys()]

    def get_preferred_title(self):
        return self.key_to_title(self.get_preferred_key())


autostorage_extension_v2 = AutostorageExtension()


@ThingProperty
class GetLocationsView(View):
    def get(self):
        global autostorage_extension_v2

        autostorage_extension_v2.check_location()
        return autostorage_extension_v2.get_locations()


@ThingProperty
@PropertySchema(fields.String(required=True, example="Default"))
class PreferredLocationView(View):
    def get(self):
        global autostorage_extension_v2

        autostorage_extension_v2.check_location()
        return autostorage_extension_v2.get_preferred_key()

    def post(self, new_path_key):
        global autostorage_extension_v2
        microscope = find_component("org.openflexure.microscope")

        if not microscope:
            abort(503, "No microscope connected. Unable to autofocus.")

        autostorage_extension_v2.check_location()
        autostorage_extension_v2.set_preferred_key(new_path_key)
        microscope.save_settings()


class PreferredLocationGUIView(View):
    @use_args({"new_path_title": fields.String(required=True)})
    def post(self, args):
        global autostorage_extension_v2

        new_path_title = args.get("new_path_title")
        logging.debug(new_path_title)

        new_path_key = autostorage_extension_v2.title_to_key(new_path_title)
        logging.debug(f"{new_path_key}")

        autostorage_extension_v2.check_location()
        autostorage_extension_v2.set_preferred_key(new_path_key)

        return new_path_title


def dynamic_form():
    global autostorage_extension_v2
    autostorage_extension_v2.check_location()
    return {
        "icon": "sd_storage",
        "title": "Storage",
        "forms": [
            {
                "name": "Autostorage",
                "isCollapsible": False,
                "isTask": False,
                "route": "/location-from-title",
                "emitOnResponse": "globalUpdateCaptures",
                "submitLabel": "Set path",
                "schema": [
                    {
                        "fieldType": "selectList",
                        "name": "new_path_title",
                        "label": "Capture storage path",
                        "options": autostorage_extension_v2.get_titles(),
                        "value": autostorage_extension_v2.get_preferred_title(),
                    }
                ],
            }
        ],
    }


autostorage_extension_v2.add_view(GetLocationsView, "list-locations")
autostorage_extension_v2.add_view(PreferredLocationView, "location")
autostorage_extension_v2.add_view(PreferredLocationGUIView, "location-from-title")
autostorage_extension_v2.add_meta(
    "gui", build_gui(dynamic_form, autostorage_extension_v2)
)
