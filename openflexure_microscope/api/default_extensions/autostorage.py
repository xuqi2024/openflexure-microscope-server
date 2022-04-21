import logging
import os
from typing import Dict, List, Optional, Tuple

import psutil
from flask import abort
from labthings import fields, find_component
from labthings.extensions import BaseExtension
from labthings.marshalling import use_args
from labthings.views import PropertyView, View

from openflexure_microscope.api.utilities.gui import build_gui
from openflexure_microscope.captures.capture_manager import (
    CaptureManager,
)
from openflexure_microscope.microscope import Microscope
from openflexure_microscope.paths import check_rw, settings_file_path

AS_SETTINGS_PATH = settings_file_path("autostorage_settings.json")


def get_partitions() -> List[str]:
    return [disk.mountpoint for disk in psutil.disk_partitions() if "rw" in disk.opts]


def get_permissive_partitions() -> List[str]:
    return [partition for partition in get_partitions() if check_rw(partition)]


def get_permissive_locations() -> List[Tuple[str, str]]:
    return [
        (partition, os.path.join(partition, "openflexure", "data", "micrographs"))
        for partition in get_permissive_partitions()
    ]


def get_current_location(capture_manager: Optional[CaptureManager]) -> str:
    if capture_manager:
        return capture_manager.paths["default"]
    else:
        raise RuntimeError(
            "Cannot get current capture location: there is no capture manager."
        )


def set_current_location(capture_manager: Optional[CaptureManager], location: str):
    if not capture_manager:
        logging.warning(
            "Cannot set_current_location of a missing capture_manager. Skipping."
        )
        return
    if not os.path.isdir(location):
        os.makedirs(location)
    logging.debug("Updating location...")
    capture_manager.paths.update({"default": location})
    logging.debug("Rebuilding captures...")
    capture_manager.rebuild_captures()
    logging.debug("Capture location changed successfully.")


def get_default_location() -> str:
    return CaptureManager.paths["default"]


def get_all_locations() -> Dict[str, str]:
    locations: Dict[str, str] = {}
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


class AutostorageExtension(BaseExtension):
    def __init__(self):
        super().__init__(
            "org.openflexure.autostorage",
            version="2.0.0",
            description="Handle switching capture storage devices",
        )

        # We'll store a reference to a CaptureManager object, who's capture paths will be modified
        self.capture_manager: Optional[CaptureManager] = None
        self.initial_location: str = get_default_location()

        # Register the on_microscope function to run when the microscope is attached
        self.on_component("org.openflexure.microscope", self.on_microscope)

        self.add_view(GetLocationsView, "/list-locations")
        self.add_view(PreferredLocationView, "/location")
        self.add_view(PreferredLocationGUIView, "/location-from-title")
        self.add_meta("gui", build_gui(self.dynamic_form, self))

    def dynamic_form(self):
        self.check_location()
        return {
            "icon": "sd_storage",
            "title": "Storage",
            "viewPanel": "gallery",
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
                            "options": self.get_titles(),
                            "value": self.get_preferred_title(),
                        }
                    ],
                }
            ],
        }

    def on_microscope(self, microscope_obj: Microscope):
        """Function to automatically call when the parent LabThing has a microscope attached."""
        logging.debug("Autostorage extension found microscope %s", microscope_obj)
        if hasattr(microscope_obj, "captures"):
            logging.debug(
                "Autostorage extension bound to CaptureManager %s", self.capture_manager
            )

            # Store a reference to the CaptureManager
            self.capture_manager = microscope_obj.captures
            # Store the initial storage location
            self.initial_location = get_current_location(self.capture_manager)

            # If preferred path does not exist, or cannot be written to
            self.check_location(self.initial_location)

            logging.debug(self.get_locations())
        else:
            raise RuntimeError(
                "Attached a microscope with no `captures` capture manager. Skipping extension."
            )

    def check_location(self, location: Optional[str] = None) -> bool:
        location = location or get_current_location(self.capture_manager)
        if not location:
            return False
        # If preferred path does not exist, or cannot be written to
        if not (os.path.isdir(location) and check_rw(location)):
            logging.error(
                "Preferred capture path %s is missing or cannot be written to. Restoring defaults.",
                location,
            )
            # Reset the storage location to default
            set_current_location(self.capture_manager, get_default_location())
        return True

    def get_locations(self) -> Dict[str, str]:
        if self.capture_manager:
            locations = get_all_locations()

            current_location = get_current_location(self.capture_manager)
            if current_location not in locations.values():
                locations.update({"Custom": current_location})
            # Add location from the CaptureManager settings file
            return locations
        else:
            return {}

    def get_preferred_key(self) -> Optional[str]:
        current = get_current_location(self.capture_manager)
        locations = self.get_locations()

        matches = [k for k, v in locations.items() if v == current]

        if len(matches) > 1:
            logging.warning(
                "Multiple path matches found. Weird, but carrying on using zeroth."
            )

        if matches:
            return matches[0]
        else:
            logging.warning("No matches found. Skipping.")
            return None

    def set_preferred_key(self, new_path_key: str):
        if not new_path_key in self.get_locations().keys():
            raise KeyError(f"No location named {new_path_key}")

        location = self.get_locations().get(new_path_key)
        if location:
            set_current_location(self.capture_manager, location)

    def key_to_title(self, path_key: Optional[str]) -> Optional[str]:
        if not path_key:
            return None
        if not path_key in self.get_locations().keys():
            raise KeyError(f"No location named {path_key}")
        return f"{path_key} ({self.get_locations().get(path_key)})"

    def title_to_key(self, path_title: str) -> str:
        matches = []
        for loc_key in self.get_locations().keys():
            if path_title.startswith(loc_key):
                matches.append(loc_key)

        if len(matches) > 1:
            logging.warning(
                "Multiple path matches found. Weird, but carrying on using zeroth."
            )

        return matches[0]

    def get_titles(self) -> List[str]:
        titles: List[str] = []
        for key in self.get_locations().keys():
            title: Optional[str] = self.key_to_title(key)
            if title:
                titles.append(title)
        return titles

    def get_preferred_title(self) -> Optional[str]:
        return self.key_to_title(self.get_preferred_key())


class GetLocationsView(PropertyView):
    def get(self):
        self.extension.check_location()
        return self.extension.get_locations()


class PreferredLocationView(PropertyView):
    schema = fields.String(required=True, example="Default")

    def get(self):
        self.extension.check_location()
        return self.extension.get_preferred_key()

    def post(self, new_path_key):
        microscope = find_component("org.openflexure.microscope")

        if not microscope:
            abort(503, "No microscope connected. Unable to autofocus.")

        self.extension.check_location()
        self.extension.set_preferred_key(new_path_key)
        microscope.save_settings()


class PreferredLocationGUIView(View):
    @use_args({"new_path_title": fields.String(required=True)})
    def post(self, args):
        new_path_title = args.get("new_path_title")
        logging.debug(new_path_title)

        new_path_key = self.extension.title_to_key(new_path_title)
        logging.debug(new_path_key)

        self.extension.check_location()
        self.extension.set_preferred_key(new_path_key)

        return new_path_title
