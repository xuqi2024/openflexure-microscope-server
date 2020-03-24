from openflexure_microscope.api.utilities import JsonResponse

from labthings.core.utilities import get_by_path, set_by_path, create_from_path

from labthings.server.find import find_component
from labthings.server.view import View

from labthings.server.decorators import ThingProperty, Tag, doc_response

from flask import jsonify, request, abort
import logging


@ThingProperty
class SettingsProperty(View):
    def get(self):
        """
        Current microscope settings, including camera and stage
        """
        microscope = find_component("org.openflexure.microscope")
        return jsonify(microscope.read_settings())

    def put(self):
        """
        Update current microscope settings, including camera and stage
        """
        microscope = find_component("org.openflexure.microscope")
        payload = JsonResponse(request)

        logging.debug("Updating settings from PUT request:")
        logging.debug(payload.json)

        microscope.update_settings(payload.json)
        microscope.save_settings()

        return self.get()


@Tag("properties")
class NestedSettingsProperty(View):
    @doc_response(404, description="Settings key cannot be found")
    def get(self, route):
        """
        Show a nested section of the current microscope settings
        """
        microscope = find_component("org.openflexure.microscope")
        keys = route.split("/")

        try:
            value = get_by_path(microscope.read_settings(), keys)
        except KeyError:
            return abort(404)

        return jsonify(value)

    @doc_response(404, description="Settings key cannot be found")
    def put(self, route):
        """
        Update a nested section of the current microscope settings
        """
        microscope = find_component("org.openflexure.microscope")
        keys = route.split("/")
        payload = JsonResponse(request)

        dictionary = create_from_path(keys)
        set_by_path(dictionary, keys, payload.json)

        microscope.update_settings(dictionary)
        microscope.save_settings()

        return self.get(route)


@ThingProperty
class StateProperty(View):
    def get(self):
        """
        Show current read-only state of the microscope
        """
        microscope = find_component("org.openflexure.microscope")
        return jsonify(microscope.state)


@Tag("properties")
class NestedStateProperty(View):
    @doc_response(404, description="Status key cannot be found")
    def get(self, route):
        """
        Show a nested section of the current microscope state
        """
        microscope = find_component("org.openflexure.microscope")
        keys = route.split("/")

        try:
            value = get_by_path(microscope.state, keys)
        except KeyError:
            return abort(404)

        return jsonify(value)


@ThingProperty
class ConfigurationProperty(View):
    def get(self):
        """
        Show current read-only state of the microscope
        """
        microscope = find_component("org.openflexure.microscope")
        return jsonify(microscope.configuration)


@Tag("properties")
class NestedConfigurationProperty(View):
    @doc_response(404, description="Configuration key cannot be found")
    def get(self, route):
        """
        Show a nested section of the current microscope state
        """
        microscope = find_component("org.openflexure.microscope")
        keys = route.split("/")

        try:
            value = get_by_path(microscope.configuration, keys)
        except KeyError:
            return abort(404)

        return jsonify(value)
