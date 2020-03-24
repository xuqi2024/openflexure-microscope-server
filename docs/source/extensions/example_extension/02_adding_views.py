from labthings.server.extensions import BaseExtension
from labthings.server.find import find_component
from labthings.server.view import View

from labthings.server.decorators import use_body
from labthings.server import fields

## Extension methods


def identify(microscope):
    """
    Demonstrate access to Microscope.camera, and Microscope.stage
    """

    response = (
        f"My name is {microscope.name}. "
        f"My parent camera is {microscope.camera}, "
        f"and my parent stage is {microscope.stage}."
    )

    return response


def rename(microscope, new_name):
    """
    Rename the microscope
    """

    microscope.name = new_name
    microscope.save_settings()


## Extension views


class ExampleIdentifyView(View):
    def get(self):
        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Return our identify function's output
        return identify(microscope)


class ExampleRenameView(View):
    # Expect a request parameter called "name", which is a string. Pass to argument "args".
    @use_body(fields.String(required=True, example="My Example Microscope"))
    def post(self, body):
        # Look for our new name in the request body
        new_name = body

        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Pass microscope and new name to our rename function
        rename(microscope, new_name)

        # Return our identify function's output
        return identify(microscope)


## Create extension

# Create your extension object
my_extension = BaseExtension("com.myname.myextension", version="0.0.0")

# Add methods to your extension
my_extension.add_method(identify, "identify")
my_extension.add_method(rename, "rename")

# Add API views to your extension
my_extension.add_view(ExampleIdentifyView, "/identify")
my_extension.add_view(ExampleRenameView, "/rename")
