from labthings.server.extensions import BaseExtension
from labthings.server.find import find_component


def identify():
    """
    Demonstrate access to Microscope.camera, and Microscope.stage
    """
    microscope = find_component("org.openflexure.microscope")

    response = (
        f"My name is {microscope.name}. "
        f"My parent camera is {microscope.camera}, "
        f"and my parent stage is {microscope.stage}."
    )

    return response


def rename(new_name):
    """
    Rename the microscope
    """

    microscope = find_component("org.openflexure.microscope")

    microscope.name = new_name
    microscope.save_settings()


# Create your extension object
my_extension = BaseExtension("com.myname.myextension", version="0.0.0")

# Add methods to your extension
my_extension.add_method(identify, "identify")
my_extension.add_method(rename, "rename")
