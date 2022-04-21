"""Load the extensions from the configuration file"""

import logging
import os

from contextlib import contextmanager
from dataclasses import dataclass, asdict
from traceback import format_exc
from typing import List, Optional, TypeVar, Type

from labthings.extensions import find_extensions, BaseExtension

T = TypeVar('T')

from openflexure_microscope.config import (
    SingleExtensionConfig,
    MicroscopeConfig,
    EXTENSION_ENTRY_POINT_GROUP,
    STAGE_ENTRY_POINT_GROUP,
    CAMERA_ENTRY_POINT_GROUP
)
from openflexure_microscope.stage.base import BaseStage
from openflexure_microscope.camera.base import BaseCamera
from openflexure_microscope.extensions.find import find_entry_point


@dataclass
class MicroscopeComponents:
    stage: BaseStage
    camera: BaseCamera
    extensions: List[BaseExtension]

@dataclass
class ExtensionLoadingResult:
    type: str
    loaded: bool
    exception: Optional[Exception] = None
    traceback: Optional[str] = None

    @property
    def json_safe_dict(self):
        """Return a dictionary without Exceptions in it, for serialisation"""
        val = asdict(self)
        for k, v in val.items():
            if isinstance(v, Exception):
                val[k] = str(v)
        return val

def load_extension(
    config: SingleExtensionConfig, 
    group_name: str,
    base_class: Type[T]=BaseExtension,
) -> T:
    """Load an extension, returning an instance"""
    ep = find_entry_point(config.type, group_name)
    extension_class = ep.load()
    instance = extension_class(**config.init_kwargs)
    if isinstance(instance, base_class):
        return instance
    else:
        raise TypeError(
            f"Extension {config.type} should be an instance of "
            f"{base_class.__name__}, but it was not."
        )

def load_legacy_extensions(extensions_folder):
    """Attempt to load old-style extensions"""
    if not os.path.isdir(extensions_folder):
        logging.warning(
            f"{extensions_folder} was specified as the old-style "
            "extensions folder, but it does not exist."
        )
        return []
    extensions = []
    for extension in find_extensions(extensions_folder):
        logging.warning(
            f"Using an old-style extension {extension.__name__}.  "
            "Support for this will be removed in the future."
        )
        extensions.append(extension)
    return extensions


def load_components(config: MicroscopeConfig) -> MicroscopeComponents:
    """Load extensions defined in config object
    
    For now, this attempts to load all the extensions defined in the
    configuration file, and return a list of extension instances.
    We also attempt to load all extensions from the folder, if the
    corresponding option is set in the config file.

    The camera and stage classes are loaded here too.
    """
    with ExtensionLoader() as e:
        camera = e.load_extension(
            config.camera, CAMERA_ENTRY_POINT_GROUP, BaseCamera
        )
        stage = e.load_extension(
            config.stage, STAGE_ENTRY_POINT_GROUP, BaseStage
        )
        extensions = [
            e.load_extension(
                ext_config, EXTENSION_ENTRY_POINT_GROUP, BaseExtension
            )
            for ext_config in config.extensions_enabled
        ]
        if config.legacy_extension_folder:
            extensions_folder = os.path.join(
                config.openflexure_dir,
                config.legacy_extension_folder
            )
            extensions += e.load_legacy_extensions(extensions_folder)


class ConfigurableComponentFailedToLoad(RuntimeError):
    """One or more optional/configurable components didn't load
    
    This exception is raised by `TryMultipleComponents`.
    It is used when we're loading several user-defined components,
    and we want to know which one(s) failed.
    """

    results: List[ExtensionLoadingResult] = None

    def __init__(
        self, results: List[ExtensionLoadingResult]
    ):
        super().__init__(self)
        self.results = results

    @property
    def summary(self):
        """A summary of which components failed, as a multiline string."""
        summary = f"Errors occurred while loading components "
        summary += "defined in the configuration:\n"
        for c in self.results:
            if c.loaded:
                summary += f"[ OK ] {c.type}\n"
            else:
                summary += f"[FAIL] {c.type}\n"
        return summary

    @property
    def json_safe_list(self):
        """A JSON-safe dictionary describing the componenents"""
        return [r.json_safe_dict for r in self.results]


class ExtensionLoader:
    """Class to keep track of extension loading progress

    The extension loader wraps `load_extension` in error handling code.
    This allows all the components of the microscope to be loaded,
    and then a helpful error message can be displayed afterwards to
    make it clear what went wrong.

    The class functions as a context manager, so you can do:

    ```
    with ExtensionLoader() as e:
       stage = e.load_extension(stage_config, ...)
       camera = e.load_extension(camera_config, ...) 
    ```

    Any errors will only be raised at the end of the `with` block.
    """

    results: List[ExtensionLoadingResult] = None

    def __init__(self):
        self.results = []

    def __enter__(self):
        """Errors will be raised at the end of a with block."""
        return self

    def __exit__(self, _exc, _value, _traceback):
        self.raise_errors()

    @contextmanager
    def suppress_error_and_save_result(self, config: SingleExtensionConfig):
        """Try a block of code, and append a result to the `results` list.
        
        Any exceptions that occur will be saved to the results and not
        propagated.
        """
        try:
            yield
            self.results.append(
                ExtensionLoadingResult(
                    type=config.type,
                    loaded=True,
                )
            )
        except Exception as e:  # pylint: disable=W0703
            logging.error(
                f"Failed loading component: {config.type}\n"
                f"Initial arguments: {config.init_kwargs}"
            )
            logging.error(format_exc())
            self.results.append(
                ExtensionLoadingResult(
                    type=config.type,
                    loaded=False,
                    exception=e,
                    traceback=format_exc(),
                )
            )

    def load_extension(
        self, 
        config: SingleExtensionConfig, 
        group_name: str,
        base_class: Type[T]=BaseExtension,
    ) -> Optional[T]:
        """Load an extension, deferring any errors until later."""
        with self.suppress_error_and_save_result(config):
            return load_extension(config, group_name, base_class=base_class)

    def load_legacy_extensions(self, extensions_folder: str):
        """Load old-style extensions from the folder, deferring errors"""
        with self.suppress_error_and_save_result(
            SingleExtensionConfig("legacy extensions")
        ):
            return load_legacy_extensions(extensions_folder)

    def raise_errors(self):
        """Check for errors and raise an exception
        
        Check for any components that did not load correctly, and raise an
        exception that includes the dictionary of results, so we can
        easily tell which one failed.
        """
        if any((v.loaded != True for v in self.results)):
            raise ConfigurableComponentFailedToLoad(
                self.results
            )
