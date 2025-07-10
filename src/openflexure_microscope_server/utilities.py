"""Utility functions and classes."""

import os
import re
from threading import Thread
import logging
from importlib.metadata import version
import tomllib

LOGGER = logging.getLogger(__name__)

REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
# Regex for a full commit hash
COMMIT_REGEX = re.compile(r"[0-9a-f]{40}")
# Regex for a reference in the git HEAD file. Group 1 is the path.
REF_REGEX = re.compile(r"^ref:\s(.*)$")


class ErrorCapturingThread(Thread):
    """Subclass of Thread that captures exceptions from the target function.

    It wraps the target function in a try-except block.

    Execution will stop with an unhandled exception, but the exception will not be raised
    until the join method is called. When the join method is called, the exception is
    called in the calling thread.

    This allows for error handling to be performed by the calling thread at the time that
    join is run.
    """

    def __init__(self, group=None, target=None, args=None, kwargs=None, daemon=None):
        """Initialise with the same arguments as Thread."""
        # As all inputs are keywords we need to set the default values for args and kwargs:
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}

        # Make an empty list for any error.
        # We are only ever going to have one or zero errors, this is an empty
        # list as we need to pass the reference not the value to collect the
        # error. If we could simply make a pointer we would have done that.
        self._error_buffer = []

        # Add the target function end error buffer to the thread to the start of
        # the argument list so they are passed to _wrap_and_catch_errors()
        args = (target, self._error_buffer, *args)
        # Start the thread with _wrap_and_catch_errors() as the target
        super().__init__(
            group=group,
            target=_wrap_and_catch_errors,
            args=args,
            kwargs=kwargs,
            daemon=daemon,
        )

    def join(self, timeout=None):
        """Join when the thread is complete.

        If the thread ended due to an unhandled exception, the exception will be raised
        when this method is called.
        """
        super().join(timeout)
        # If there is an error in the error buffer clear the buffer and raise it
        if self._error_buffer:
            err = self._error_buffer[0]
            self._error_buffer = []
            raise err


def _wrap_and_catch_errors(target, error_buffer, *args, **kwargs):
    """Run target function in a try-except block.

    This function is designed only to be used by ErrorCapturingThread.

    It will run a target function in a try-except block catching any exception.
    If an exception is caught it is added to ``error_buffer``.

    :param target: The target function to call
    :param error_buffer: An empty list that is used for returning the exception from
        the thread. It is a list to ensure it is passed by reference.
    :param ``*args``: The arguments for the target function
    :param ``**kwargs``: The Keyword arguments for the target function
    """
    try:
        target(*args, **kwargs)
    except BaseException as e:
        error_buffer.append(e)


def robust_version_strings() -> tuple[str, str]:
    project_toml_path = os.path.join(REPO_DIR, "pyproject.toml")
    git_dir_path = os.path.join(REPO_DIR, ".git")
    has_project_toml = os.path.isfile(project_toml_path)
    has_git_dir = os.path.isdir(git_dir_path)

    if has_project_toml and has_git_dir:
        # .git dir and pyproject.toml available. This is a development
        # installation.
        ver = "v" + _get_version_from_toml(project_toml_path)
        source = _get_hash_from_git_dir(git_dir_path)
    elif has_project_toml:
        # Only pyproject.toml available. Likely installed from source. Check
        # file directly as `importlib.metadata.version` plays badly with editable
        # installs.
        ver = "v" + _get_version_from_toml(project_toml_path)
        source = "TOML"
    elif has_git_dir:
        # Only .git dir, that is weird.
        LOGGER.warning(
            "Unexpected installation cofiguration. Version number cannot be verified."
        )
        ver = "Undefined"
        source = _get_hash_from_git_dir(git_dir_path)
    else:
        # "Neither probably installed from wheel. Note this can
        # be unreliable if the package is not installed as a distribution.
        # This is why it is the last option.
        ver = "v" + version("openflexure_microscope_server")
        source = "Dist"
    return (ver, source)


def _get_hash_from_git_dir(git_dir_path: str) -> str:
    head_path = os.path.join(git_dir_path, "HEAD")
    try:
        with open(head_path, "r", encoding="utf-8") as head_file:
            head = head_file.read()
    except IOError:
        LOGGER.error("Problem opening .git/HEAD")
        return "Undefined"
    # The file HEAD should either be a reference or commit ID.
    if match := COMMIT_REGEX.match(head):
        return match.group(0)
    if match := REF_REGEX.match(head):
        ref_path = os.path.join(git_dir_path, match.group(1))
        return _get_hash_from_git_ref(ref_path)
    LOGGER.error("Unexpected format for .git/HEAD")
    return "Undefined"


def _get_hash_from_git_ref(git_ref_path: str) -> str:
    with open(git_ref_path, "r", encoding="utf-8") as ref_file:
        ref = ref_file.read()
    if ref_match := COMMIT_REGEX.match(ref):
        return ref_match.group(0)
    LOGGER.error("No hash found in Git ref")
    return "Undefined"


def _get_version_from_toml(toml_path: str) -> str:
    try:
        with open(toml_path, "rb") as toml_file:
            toml_dict = tomllib.load(toml_file)
        return toml_dict["project"]["version"]
    except (IOError, ValueError, KeyError):
        LOGGER.error("Problem opening .git/HEAD")
        return "Undefined"
