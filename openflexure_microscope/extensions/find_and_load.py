"""
Code to locate and load microscope extensions.

Some of this may in due course make it in to LabThings.

"""

import argparse
import logging
import shlex
import subprocess
import traceback
from ..utilities import ensure_root_privileges, running_as_root

try:
    from importlib import metadata
except ImportError:
    logging.info("importlib.metadata not present, using importlib_metadata")
    import importlib_metadata as metadata

EXTENSION_GROUP_NAME = "openflexure_microscope_extensions"

def entry_point_list(group_name=EXTENSION_GROUP_NAME):
    """Return a list of entry points in a particular group.
    
    This uses the importlib metadata mechanism to enumerate entry points
    declared in installed packages.  By default, it will list all entry
    points belonging to the group for OFM extensions.

    A list of EntryPoint objects is returned, which may be empty.
    """
    try:
        group_name = "openflexure_microscope_extensions"
        return metadata.entry_points()[group_name]
    except KeyError:
        return []

def find_and_load_extensions():
    """Locate all extensions that declare themselves as entry points.
    
    Each extension will be loaded, to determine if it can load, and whether
    further configuration is needed.
    """
    entry_points = entry_point_list(EXTENSION_GROUP_NAME)
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


def filter_extension_list(extensions, status):
    """Return a subset of extensions matching a particular status"""
    return [ext for ext in extensions if ext["status"] == status]

def print_extension_list(extensions):
    """Pretty-print a list of extensions from the output of `find_and_load_extensions`"""
    for ext in extensions:
            print(f"* {ext['name']}: {ext['status']} (from {ext['value']})")

def print_extensions_by_status(extensions):
    """Print extensions, sorted by their status."""
    for status, message in [
        ("loaded", "The following extensions are installed and could be loaded:"),
        ("broken", "The following extensions are installed but cannot be loaded or automatically fixed:"),
        ("install_script_required", "The following extensions cannot be loaded, but suggest a script that could fix them:"),
        ("configuration_required", "The following extensions require configuration before they will work properly:")
    ]:
        subset = filter_extension_list(extensions, status)
        if len(subset) > 0:
            print(message)
            print_extension_list(subset)
            print()

def yes_no_prompt():
    """Ask for a yes/no answer on the command line."""
    return input("(enter Y or N):").tolower().startswith("y")

def run_installation_commands(extensions, skip_admin_check=False):
    """For each extension, if it suggests running a command so it can load, interactively run that command."""
    if not skip_admin_check:
        ensure_root_privileges()
    ensure_root_privileges()
    for ext in extensions:
        if ext['status'] != "install_script_required":
            print(f"Skipping {ext['name']}")
            continue
        print(f"Extension '{ext['name']}' cannot load, but suggests we run the following script:")
        print(ext['install_script'])
        print("Would you like to run that script?  This will be run with administrative")
        print("privileges, so only answer Y if you trust the authors of the extension.")
        if yes_no_prompt():
            try:
                completed_process = subprocess.run(ext['install_script'], shell=True, )
                completed_process.check_returncode()
                print("SUCCESS")
            except subprocess.CalledProcessError:
                print("The installation command failed: see output above for details.")
                print("This probably means you need to fix system-level dependencies manually.")
                print("Press enter to continue...")
                input()
        print()


def configure_extensions(extensions, skip_admin_check=False):
    """Run the configuration method of any extensions that request it."""
    if not skip_admin_check:
        ensure_root_privileges()
    for ext in extensions:
        if ext['status'] != "configuration_required":
            print(f"Skipping {ext['name']}")
            continue
        print(f"Extension '{ext['name']}' cannot run, but has a configuration routine.")
        print("Would you like to configure this extension? This will be run with administrative")
        print("privileges, so only answer Y if you trust the authors of the extension.")
        if yes_no_prompt():
            try:
                ext['extension'].configure_extension()
                print("SUCCESS")
            except Exception as e: # pylint: disable=W0703
                print(f"Error configuring {ext['name']}:")
                traceback.print_exc()
                print("Error: the configuration method did not succeed.  Error information")
                print("is above this message.")
                print("Press enter to continue...")
                input()
        print()


def check_extensions_cmd():
    """Check available extensions, and list their status (for the command line utility)"""
    parser = argparse.ArgumentParser(description="""Check available extensions, showing which can be loaded and which require attention.""")
    parser.add_argument("-u", "--user", action="store_true", help="Skip the check for administrative privileges (use if your installation is user-writeable).")
    args = parser.parse_args()
    extensions = find_and_load_extensions()

    print("The following extensions were found:")
    print_extension_list(extensions)
    print()
    print_extensions_by_status(extensions)
    
    install_required = filter_extension_list(extensions, "install_script_required")
    configuration_required = filter_extension_list(extensions, "configuration_required")

    # If there are no extensions needing attention, stop here
    if len(install_required) == 0 or len(configuration_required) == 0:
        exit(0)

    print("Some extensions require configuration.  Would you like to set them up now?")
    if not yes_no_prompt():
        exit(0)

    run_installation_commands(install_required, skip_admin_check=args.user)
    configure_extensions(configuration_required, skip_admin_check=args.user)
    


def install_extension_cmd():
    """Install a Python package, then check for extensions that need to be fixed or enabled."""
    parser = argparse.ArgumentParser(description="Install an extension from a Python package via pip")
    parser.add_argument("package_name", help="The name of the package to install, as expected by pip")
    parser.add_argument("-u", "--user", action="store_true", help="Skip the check for administrative privileges (use if your installation is user-writeable).")
    args = parser.parse_args()
    if not args.user:
        ensure_root_privileges()
    print(f"Installing '{args.package_name}'...")
    subprocess.run(["pip", "install", args.package_name])
    print("Please now run ofm-check-extensions to ensure your new extension is installed properly.")

if __name__ == "__main__":
    check_extensions_cmd()
    
