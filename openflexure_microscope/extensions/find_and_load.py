"""
Code to locate and load microscope extensions.

Some of this may in due course make it in to LabThings.

"""


import logging

try:
    from importlib import metadata
except ImportError:
    logging.info("importlib.metadata not present, using importlib_metadata")
    import importlib_metadata as metadata


def find_and_load_extensions():
    """Locate all extensions that declare themselves as entry points.
    
    Each extension will be loaded, to determine if it can load, and whether
    further configuration is needed.
    """
    try:
        group_name = "openflexure_microscope_extensions"
        entry_points = metadata.entry_points()[group_name]
    except KeyError:
        return []
    extensions = []
    for p in entry_points:
        ext = {"name": p.name, "value": p.value, "status": "unknown"}
        try:
            ext["extension"] = p.load()
            if ext["extension"].configuration_required():
                ext["status"] = "configuration_required"
            else:
                ext["status"] = "loaded"
        except ImportError as err:
            # TODO: think of a method that is less platform-specific!
            if hasattr(err, "of_raspbian_install_script"):
                ext["status"] = "install_script_required"
                ext["install_script"] = err.of_raspbian_install_script
            else:
                ext["status"] = "broken"
            ext["import_error"] = err
            extensions.append(ext)
    return extensions

def display_extension_status(extensions):
    """Print the status of each installed extension"""
    for ext in extensions:
        print(f"{ext['name']:<32} [{ext['status']}] (from {ext['value']})")

    # Find extensions that don't load because they need pre-install scripts to be run
    install_required = [ext for ext in extensions if ext["status"] == "install_script_required"]
    if len(install_required) > 0:
        print("Some extensions require prerequisites to be installed before they can be loaded:")
        for ext in install_required:
            print(f"**{ext['name']}** (from {ext['value']}) suggests:")
            print(ext["install_script"])
            print()

    configuration_required = [ext for ext in extensions if ext["status"] == "configuration_required"]
    if len(configuration_required) > 0:
        print("Some extensions need you to run their post-install configuration script before they will work:")
        for ext in configuration_required:
            print(f"**{ext['name']}** (from {ext['value']})")

if __name__ == "__main__":
    extensions = find_and_load_extensions()
    display_extension_status(extensions)
    
    
