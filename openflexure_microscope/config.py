"""
Microscope configuration

This file defines the structure of configuration data, along with functions to
manipulate it and process configuration arguments.

The config file is the top-level configuration of the microscope.  It sets the
modules that get loaded, and can also specify the various paths used.

The dataclass `MicroscopeConfig` defines the structure of the configuration
file; it is loaded with the `dacite` package which handles validation.

Currently, the paths used by the microscope are specified by two keys:

:openflexure_dir: sets the location of the top-level folder, inside whic
we put settings, logs, etc.
:legacy_extensions_folder: sets the location of the microscope extensions
folder, for old-style extensions.  By default, this does not exist, as 
old-style extensions are now deprecated.  This path is relative to the 
`openflexure_dir` folder.

In the future, more granular control of paths (e.g. log paths) may be
possible.
"""
import argparse
import json
import logging
import os
import dacite
import dataclasses as dc
from typing import List, Optional

from openflexure_microscope import paths
from openflexure_microscope.extensions.find import list_entry_point_values


EXTENSION_ENTRY_POINT_GROUP = "labthings.extensions"
CAMERA_ENTRY_POINT_GROUP = "openflexure_microscope.cameras"
STAGE_ENTRY_POINT_GROUP = "openflexure_microscope.stages"


@dc.dataclass
class SingleExtensionConfig:
    """Define the entry point and arguments used for an extension
    
    :param type: The value of an entry point, i.e. a string in the format
       `module.submodule.etc:ClassName`.  This must be declared by its
       module as an entry point in the group `labthings.extensions`, or
       a more specific group in the case of stages and cameras.
    :param init_kwargs: is an optional dictionary, which is passed as
       keyword arguments to the constructor of the class defined in `type`
       when the extension is loaded.
    """

    type: str
    init_kwargs: dict = dc.field(default_factory=dict)


@dc.dataclass
class MicroscopeConfig:
    """Define all the entry points needed for a microscope
    """

    config_file_version: str
    camera: SingleExtensionConfig
    stage: SingleExtensionConfig
    extensions_enabled: List[SingleExtensionConfig] = dc.field(default_factory=list)
    extensions_disabled: List[SingleExtensionConfig] = dc.field(default_factory=list)
    legacy_extension_folder: Optional[str] = None
    openflexure_dir: str = dc.field(default_factory=paths.default_openflexure_dir)

    def enable_extension(self, type: str):
        """Enable an extension by moving it to `extensions_enabled`
    
        NB this does not take effect until the server is restarted.  It will
        also not be written to disk automatically, only this object is 
        affected.
        """
        move_extension_between_lists(
            type, self.extensions_disabled, self.extensions_enabled
        )

    def disable_extension(self, type: str):
        """Disable an extension by moving it to `extensions_disabled`
    
        NB this does not take effect until the server is restarted.  It will
        also not be written to disk automatically, only this object is 
        affected.
        """
        move_extension_between_lists(
            type, self.extensions_enabled, self.extensions_disabled
        )

    @property
    def all_extensions(self):
        """All SingleExtensionConfig objects in this configuration instance"""
        extensions = []
        for f in dc.fields(self):
            val = getattr(self, f.name)
            if isinstance(val, SingleExtensionConfig):
                extensions.append(val)
            elif isinstance(val, list):
                for v in val:
                    if isinstance(SingleExtensionConfig):
                        extensions.append(v)
            elif isinstance(val, dict):
                for v in val.values():
                    if isinstance(SingleExtensionConfig):
                        extensions.append(v)
        return extensions

    def find_extension(self, type: str) -> Optional[SingleExtensionConfig]:
        """Return the extension matching the given `type`, if it is in the config."""
        return find_extension_by_type(type, self.all_extensions)

    def to_dict(self) -> dict:
        """Return the configuration as a simple dictionary"""
        return dc.asdict(self)


def microscope_config_from_dict(value: dict) -> MicroscopeConfig:
    """Convert a dictionary to a microscope config object"""
    return dacite.from_dict(MicroscopeConfig, value)


def find_extension_by_type(
    type: str, extensions: List[SingleExtensionConfig]
) -> Optional[SingleExtensionConfig]:
    """Search a list of extension configurations for one matching the given type"""
    for e in extensions:
        if e.type == type:
            return e
    return None


def move_extension_between_lists(
    type: str,
    from_list: List[SingleExtensionConfig],
    to_list: List[SingleExtensionConfig],
):
    """Move the extension with a given type from one list to another.

    If the extension exists in `from_list`, it is moved over.  If not, a new
    `SingleExtensionConfig` object is created and added to `to_list`.
    """
    from_extension = find_extension_by_type(type, from_list)
    if from_extension:
        from_list.remove(from_extension)
    to_extension = find_extension_by_type(type, to_list)
    if to_extension:
        logging.warning(
            f"Attempting to add extension {type}, to list {to_list} but it was already there!"
        )
    elif from_extension:
        # If we found the extension in the from_list, move it to the destination
        to_list.append(from_extension)
    else:
        # Otherwise, create a new config entry with no initial parameters
        to_list.append(SingleExtensionConfig(type=type))


def add_config_args(parser: argparse.ArgumentParser):
    """Add arguments relating to the configuration file."""
    parser.add_argument("--config", "-c", help="Set the configuration file to use.")
    parser.add_argument(
        "--config_literal",
        help=(
            "A JSON literal specifying the server configuration. "
            "This overrides the config file and the --config option."
        ),
    )


def load_config(args: Optional[argparse.Namespace] = None):
    """Load the configuration from a file or command-line argument"""
    if args:
        # If a literal configuration is given, read it from the command line argument.
        if args.config_literal:
            return microscope_config_from_dict(json.loads(args.config_literal))
        # If a configuration file is given, check it exists and use it
        if args.config:
            if os.path.isfile(args.config):
                with open(args.config, "r") as f:
                    return microscope_config_from_dict(json.load(f))
            else:
                raise FileNotFoundError(
                    f"The specified configuration file '{args.config}' does not exist."
                )
    else:
        config_file = paths.first_path_that_exists(paths.CONFIG_FILE_SEARCH_PATH)
        if config_file:
            print(f"Loading configuration from '{config_file}'.")
            with open(config_file, "r") as f:
                return microscope_config_from_dict(json.load(f))
        else:
            raise FileNotFoundError(
                "We could not find any config files in the default search locations. "
                f"tried: {paths.CONFIG_FILE_SEARCH_PATH}."
            )


def default_config():
    """Generate default configuration values
    
    This does not attempt to create a configuration file, just generate a
    valid configuration object.
    
    By default, we will attempt to use a SangaStage and a PiCameraStreamer, and
    enable all the default extensions (but no others).  This should not be relied
    upon and may change in the future.
    """
    return MicroscopeConfig(
        config_file_version="v3.0.0-alpha0",
        camera=SingleExtensionConfig(
            "openflexure_microscope.camera.pi:PiCameraStreamer"
        ),
        stage=SingleExtensionConfig(
            type="openflexure_microscope.stage.sanga:SangaStage",
            init_kwargs={"port": None},
        ),
        extensions_enabled=[
            SingleExtensionConfig(name, {})
            for name in list_entry_point_values(EXTENSION_ENTRY_POINT_GROUP)
            if name.startswith("openflexure_microscope.api.default_extensions")
        ],
        legacy_extension_folder="microscope_extensions",
    )
