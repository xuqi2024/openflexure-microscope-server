"""
Code to locate and load microscope extensions.

Some of this may in due course make it in to LabThings.

"""

import argparse
import logging
import shlex
import subprocess
import traceback

from ..utilities import ensure_root_privileges
from . import config
from .find import extension_entry_points, entry_points_from_list

def load_extension_dict(entry_point):
    """Attempt to load an extension from an entry point, returning a dict"""
    p = entry_point
    ext = {"name": p.name, "value": p.value, "status": "unknown", "config": "missing from config"}
    if p.value in config.extensions_enabled():
        ext["config"] = "enabled"
    if p.value in config.extensions_disabled():
        ext["config"] = "disabled"

    try:
        ext["extension"] = p.load()
        ext["status"] = "loaded"
        try:
            if ext["extension"].configuration_required():
                ext["status"] = "configuration_required"
        except AttributeError:
            pass # If `configuration_required` is missing, assume no action is needed
    except ImportError as err:
        # TODO: think of a method that is less platform-specific!
        if hasattr(err, "of_raspbian_install_script"):
            ext["status"] = "install_script_required"
            ext["install_script"] = err.of_raspbian_install_script
        else:
            ext["status"] = "broken"
        ext["import_error"] = err
    except Exception as e: # pylint: disable=W0703
        ext["status"] = "broken"
        ext["import_error"] = e
    return ext


def filter_extension_list(extensions, status=None, config=None):
    """Return a subset of extensions matching a particular status"""
    return [
        ext for ext in extensions 
            if ext["status"] == status or status is None
            if ext["config"] == config or config is None
        ]


def print_extension_list(extensions):
    """Pretty-print a list of extension status dictionaries"""
    for ext in extensions:
            print(f"* {ext['name']}: {ext['status']}, {ext['config']} (from {ext['value']})")


def print_extensions_by_status(extensions):
    """Print extensions, sorted by their status."""
    for status, config, message in [
        ("loaded", None, "The following extensions are installed and could be loaded:"),
        ("broken", None, "The following extensions are installed but cannot be loaded or automatically fixed:"),
        ("install_script_required", None, "The following extensions cannot be loaded, but suggest a script that could fix them:"),
        ("configuration_required", None, "The following extensions require configuration before they will work properly:"),
        (None, "missing from config", "The following extensions are neither enabled nor explicitly disabled:")
    ]:
        subset = filter_extension_list(extensions, status=status, config=config)
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
    print("Checking for extensions that require system-level dependencies...")
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
    print("Checking and configuring extensions...")
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
    parser.add_argument("-a", "--all", action="store_true", help="Attempt to load all plugins, rather than just the enabled ones")
    args = parser.parse_args()

    if args.all:
        entry_points = extension_entry_points()
    else:
        entry_points = entry_points_from_list(config.extensions_enabled(), fail_on_missing=True)
    extensions = [load_extension_dict(p) for p in entry_points]

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
    """Install a Python package, then check for new extensions that need to be fixed or enabled."""
    parser = argparse.ArgumentParser(description="Install an extension from a Python package via pip")
    parser.add_argument("package_name", help="The name of the package to install, as expected by pip")
    parser.add_argument("-u", "--user", action="store_true", help="Skip the check for administrative privileges (use if your installation is user-writeable).")
    args = parser.parse_args()
    if not args.user:
        ensure_root_privileges()

    preinstall_eps = extension_entry_points()
    try:
        print(f"Installing '{args.package_name}'...")
        completed_process = subprocess.run(["pip", "install", args.package_name])
        completed_process.check_returncode()
    except subprocess.CalledProcessError:
        print("The installation command failed: see output above for details.")
        exit(completed_process.returncode)
    postinstall_eps = extension_entry_points()
    new_eps = [ep for ep in postinstall_eps if ep not in preinstall_eps]
    if len(new_eps) == 0:
        print(
            "We did not find any newly-installed extensions. Please run ofm-check-extensions"
            "to ensure your new extension is installed properly."
        )
        exit(-1)
    new_extensions = [load_extension_dict(p) for p in new_eps]
    print("Installed the following extensions:")
    print_extension_list(new_extensions)
    print()
    run_installation_commands(new_extensions, skip_admin_check=args.user)
    new_extensions = [load_extension_dict(p) for p in new_eps] # reload, in case some are now fixed
    configure_extensions(new_extensions, skip_admin_check=args.user)
    new_extensions = [load_extension_dict(p) for p in new_eps] # reload, in case some are now fixed
    for ext in new_extensions:
        if ext["status"] == "loaded":
            config.enable_extension(ext["value"])
            print(f"Enabled extension {ext['value']}")
        else:
            config.disable_extension(ext["value"])
            print(f"Disabled extension {ext['value']} as it's not loadable")
            

    print("All done :)")

def enable_disable_extension_cmd(action: str):
    parser = argparse.ArgumentParser(description=f"{action} a microscope extension.")
    parser.add_argument("entry_point", help="The module and object of the extension, in the format module.submodule:ClassName.")
    args = parser.parse_args()
    try:
        _ = entry_points_from_list([args.entry_point], fail_on_missing=True)
    except ValueError:
        print("The entry point you specified was not found.  Valid entry points are listed below:")
        for ep in extension_entry_points():
            print(ep.value)
    
    if action=="enable":
        config.enable_extension(args.entry_point)
    elif action=="disable":
        config.disable_extension(args.entry_point)
def enable_extension_cmd():
    enable_disable_extension_cmd("enable")
def disable_extension_cmd():
    enable_disable_extension_cmd("disable")

if __name__ == "__main__":
    check_extensions_cmd()
    
