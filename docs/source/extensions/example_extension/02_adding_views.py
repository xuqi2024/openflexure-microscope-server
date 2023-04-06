from labthings import fields, find_component
from labthings.extensions import BaseExtension
from labthings.views import View


# Create the extension class
class MyExtension(BaseExtension):
    def __init__(self):
        # Superclass init function
        super().__init__("com.myname.myextension", version="0.0.0")

        # Add our API Views (defined below MyExtension)
        self.add_view(ExampleIdentifyView, "/identify")
        self.add_view(ExampleRenameView, "/rename")

    def identify(self, microscope):
        """
        Demonstrate access to Microscope.camera, and Microscope.stage
        """
        response = (
            f"My name is {microscope.name}. "
            f"My parent camera is {microscope.camera}, "
            f"and my parent stage is {microscope.stage}."
        )

        return response

    def rename(self, microscope, new_name):
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
        return self.extension.identify(microscope)


class ExampleRenameView(View):
    # Expect a request parameter called "name", which is a string.
    # Passed to the argument "args".
    args = fields.String(required=True, metadata={"example": "My Example Microscope"})

    def post(self, args):
        # Look for our new name in the request body
        new_name = args

        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Pass microscope and new name to our rename function
        self.extension.rename(microscope, new_name)

        # Return our identify function's output
        return self.extension.identify(microscope)


LABTHINGS_EXTENSIONS = (MyExtension,)
