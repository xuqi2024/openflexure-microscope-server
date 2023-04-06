from labthings import Schema, fields, find_component
from labthings.extensions import BaseExtension
from labthings.views import PropertyView


# Create the extension class
class MyExtension(BaseExtension):
    def __init__(self):
        # Superclass init function
        super().__init__("com.myname.myextension", version="0.0.0")

        # Add our API Views (defined below MyExtension)
        self.add_view(ExampleIdentifyView, "/identify")
        self.add_view(ExampleRenameView, "/rename")

    def rename(self, microscope, new_name):
        """
        Rename the microscope
        """
        microscope.name = new_name
        microscope.save_settings()


# Define which properties of a Microscope object we care about,
# and what types they should be converted to
class MicroscopeIdentifySchema(Schema):
    name = fields.String()  # Microscopes name
    id = fields.UUID()  # Microscopes unique ID
    state = fields.Dict()  # Status dictionary
    camera = fields.String()  # Camera object (represented as a string)
    stage = fields.String()  # Stage object (represented as a string)


## Extension viewss

# Since we only have a GET method here, it'll register as a read-only property
class ExampleIdentifyView(PropertyView):
    # Format our returned object using MicroscopeIdentifySchema
    schema = MicroscopeIdentifySchema()

    def get(self):
        """
        Show identifying information about the current microscope object
        """
        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Return our microscope object,
        # let schema handle formatting the output
        return microscope


# We can use a single schema as the input and output will be formatted identically
# Eg. We always expect a "name" string argument, and always return a "name" string attribute
class ExampleRenameView(PropertyView):
    schema = {
        "name": fields.String(
            required=True, metadata={"example": "My Example Microscope"}
        )
    }

    def get(self):
        """
        Show the current microscope name
        """
        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        return microscope

    def post(self, args):
        """
        Change the current microscope name
        """
        # Look for our "name" parameter in the request arguments
        new_name = args.get("name")

        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Pass microscope and new name to our rename function
        self.extension.rename(microscope, new_name)

        # Return our microscope object,
        # let schema handle formatting the output
        return microscope


LABTHINGS_EXTENSIONS = (MyExtension,)
