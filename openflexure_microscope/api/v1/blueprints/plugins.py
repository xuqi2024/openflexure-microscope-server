from openflexure_microscope.api.v1.views import MicroscopeViewPlugin

from flask import Blueprint, jsonify
from openflexure_microscope.api.v1.views import MicroscopeView

import logging
import warnings

class PluginSchemaAPI(MicroscopeView):
    def get(self):
        """
        Return the current plugin schemas

        .. :quickref: Plugin; Get schemas

        """
        out = self.microscope.plugin.schemas
        return jsonify(out)


def construct_blueprint(microscope_obj):

    blueprint = Blueprint('plugin_blueprint', __name__)

    # Create a base route to return plugin API schemas, if any exist
    blueprint.add_url_rule(
        '/',
        view_func=PluginSchemaAPI.as_view('plugin_api_schema', microscope=microscope_obj)
    )

    all_routes = []

    # For each plugin attached to the microscope object
    for plugin_name, plugin_obj in microscope_obj.plugin.plugins:

        # If plugin contains valid endpoints
        if hasattr(plugin_obj, 'api_views') and isinstance(plugin_obj.api_views, dict):

            # We'll keep a record of how each route was expanded
            expanded_routes = {}

            # For each defined endpoint
            for view_route, view_class in plugin_obj.api_views.items():

                # Remove all leading slashes from view route
                cleaned_route = view_route
                while cleaned_route[0] == '/':
                    cleaned_route = cleaned_route[1:]

                # Construct a full view route from the plugin name
                full_view_route = "/{}/{}".format(plugin_name, cleaned_route)
                logging.debug(full_view_route)

                # Record how the view_route got expanded
                expanded_routes[view_route] = full_view_route

                # Check if endpoint name clashes
                if full_view_route not in all_routes and issubclass(view_class, MicroscopeViewPlugin):
                    # Add route to main route dictionary
                    all_routes.append(full_view_route)

                    # Create a Python-safe name for the route
                    plugin_route_id = 'plugin{}'.format(full_view_route).replace('/', '_')

                    # Add route to the plugins blueprint
                    blueprint.add_url_rule(
                        full_view_route,
                        view_func=view_class.as_view(
                            plugin_route_id,
                            microscope=microscope_obj,
                            plugin=plugin_obj
                        )
                    )

                else:
                    warnings.warn(
                        "An endpoint /{} has already been loaded. Skipping {}.".format(
                            full_view_route,
                            view_class
                        )
                    )

            # If plugin includes an API schema
            if hasattr(plugin_obj, 'api_schema') and isinstance(plugin_obj.api_schema, dict):
                schema = plugin_obj.api_schema
                # TODO: Validate schema? We need to make sure no single plugin can break all plugins.
                schema['id'] = plugin_name
                if 'forms' in schema and isinstance(schema['forms'], list):
                    for form in schema['forms']:
                        if 'route' in form and form['route'] in expanded_routes.keys():
                            form['route'] = expanded_routes[form['route']]
                        else:
                            logging.warn("No valid expandable route found for {}".format(form['route']))
                
                # Store the complete schema in Microscope().plugin.schema
                microscope_obj.plugin.schemas.append(schema)

        else:
            warnings.warn(
                "No valid 'api_views' dictionary found in {}".format(plugin_obj)
            )
    return blueprint
