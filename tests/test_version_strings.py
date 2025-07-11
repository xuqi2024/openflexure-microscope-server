"""Tests that version strings can be produced reliably."""

import subprocess
import os
import re
import tempfile

from hypothesis import strategies as st

from openflexure_microscope_server import utilities


# This is the regex provided by https://semver.org/
SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# Use hypothesis to generate random filenames
FILE_NAME_GEN = st.from_regex(r"[a-zA-Z_-]{5,20}\.[a-z]{1,5}", fullmatch=True)
# Use hypothesis to generate random data for files
FILE_Data_GEN = st.from_regex(r"[a-zA-Z_-]{5,20}\.[a-z]{1,5}", fullmatch=True)


def _git(command: str) -> str:
    """Run a git command in a subprocess."""
    git_command = ["git"] + command.split()
    # Use check=True so an error is raised if git has a problem. Only read STDOUT
    result = subprocess.run(git_command, shell=True, check=True, capture_output=True)
    return result.stdout.decode()


def test_reading_hash_from_git():
    """Use create a Git repo and check that hash can be read.

    The performs a series of directory and git operations, commented as they go.
    """
    working_dir = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            git_dir = os.path.join(tmpdir, ".git")
            # Git dir not created yet. Returns Undefined
            assert utilities._get_hash_from_git_dir(git_dir) == "Undefined"

            # Intialised. Should still be undefined.
            _git("init")
            assert utilities._get_hash_from_git_dir(git_dir) == "Undefined"

    finally:
        # Return to original working dir
        os.chdir(working_dir)


def test_reading_version_from_toml():
    """Check version string can be read from this project's TOML file.

    As we only expect to ever read our own TOML file there is not a need to do
    excessive testing on different generated TOML files.
    """
    project_toml_path = os.path.join(utilities.REPO_DIR, "pyproject.toml")
    ver_string = utilities._get_version_from_toml(project_toml_path)
    # Check version does follow semantic versioning.
    assert SEMVER_REGEX.match(ver_string)
    # Explicit check
    assert ver_string == "3.0.0-alpha1"


def test_error_reading_version_from_toml():
    """Check Undefined is returned if error reading TOML file."""
    # Just give it the wrong path.
    project_toml_path = os.path.join(utilities.REPO_DIR, "pyppproject.toml")
    ver_string = utilities._get_version_from_toml(project_toml_path)
    # Explicit check
    assert ver_string == "Undefined"
