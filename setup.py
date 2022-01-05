"""A setuptools based setup module for the OpenFlexure Microscope server

This file was prepared according to:
https://packaging.python.org/guides/distributing-packages-using-setuptools/


"""

from os import path

# the following imports, from the guide above, prefer `setuptools` to `distutils`
from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

# Not all arguments to `setup()` are required for upload to PyPI.
# See the tutorial linked to at the top for which ones are needed.

setup(
    name="openflexure-microscope-server",
    version="2.10.0",
    description="Python module, and Flask-based web API, to run the OpenFlexure Microscope.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.openflexure.org",  # "home-page" metadata field
    author="Joel Collins, Richard Bowman, Julian Stirling",
    author_email="contact@openflexure.org",
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    # NB declaring Python versions here doesn't affect dependency resolution - it's for info only.
    classifiers=["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],
    keywords="raspberry pi arduino microscope",  # Optional
    packages=find_packages(exclude=["contrib", "docs", "tests", "*node_modules*"]),
    python_requires="== 3.7.*",
    # This field lists other packages that your project depends on to run.
    # Any package you put here will be installed by pip when your project is
    # installed, so they must be valid existing projects.
    #
    # These dependencies specify relatively flexible versions; Pipenv then resolves these
    # to specific versions, and locks those versions in ``Pipfile``.  Usually, when you
    # set up the project for development, you use those specific packages, rather than
    # the looser specifications given here.
    install_requires=[
        "apispec[validation]",  # We need the extra to validate the spec
        "Flask ~= 1.0",
        "Pillow ~= 7.2.0",
        "numpy ~= 1.20",
        "scipy ~= 1.6.1",
        "python-dateutil ~= 2.8",
        "psutil ~= 5.6.7",  # Autostorage extension
        "opencv-python-headless ~= 4.5.1",
        "sangaboard ~= 0.2",
        "expiringdict ~= 1.2.1",
        "camera-stage-mapping == 0.1.4",
        "picamerax ~= 20.9.1",
        "pyyaml ~= 5.4.0",
        "pytest-cov ~= 2.10.1",
        "piexif ~= 1.1.3",
        "labthings ~= 1.3.0",
        "typing-extensions ~= 3.7.4",  # Needed for some type-hints in Python < 3.8 (e.g. Literal)
        "RPi.GPIO ~= 0.7.0; platform_machine == 'armv7l'",
    ],
    # "dev" specifies extra packages used for development (linting, testing, etc.)
    # As with install_requires, these are relatively loose versions - Pipfile will then lock
    # them to specific versions to enable consistent builds and testing.
    extras_require={
        "dev": [
            "sphinx < 4.0",  # Currently httpdomain isn't ready for 4.0
            "sphinxcontrib-openapi ~= 0.7",
            "sphinx_rtd_theme ~=0.5.2",
            "rope ~= 0.14.0",
            "pylint ~= 2.8.0",  # 2.9.2 crashes and I've not yet figured out why.
            "pytest ~= 6.1.2",
            "mypy ~= 0.790",
            "types-python-dateutil",
            "types-setuptools",
            "poethepoet ~= 0.10.0",
            "freezegun ~= 1.0.0",
            "lxml ~= 4.6",
            "black == 18.9b0",  # Because black is in prerelease, giving a flexible version
            # specifier causes all manner of problems.  A fixed version
            # avoids issues with prereleases (which are normally not
            # allowed by pipenv) but can be a bit of a pain sometimes!
        ]
    },
    dependency_links=[],
    # We create some "entry points" to make it easier to run important modules
    entry_points={
        "console_scripts": [
            "ofm-serve=openflexure_microscope.api.app:ofm_serve",
            "ofm-rescue=openflexure_microscope.rescue.auto:main",
            "ofm-generate-openapi=openflexure_microscope.api.app:generate_openapi",
            "ofm-install-extension=openflexure_microscope.extensions.find_and_load:install_extension_cmd",
            "ofm-check-extensions=openflexure_microscope.extensions.find_and_load:check_extensions_cmd"
        ],
        "openflexure_microscope_stages": [
            "ofm-missing-stage=openflexure_microscope.stage.mock:MissingStage",
            "ofm-sanga-stage=openflexure_microscope.stage.sanga:SangaStage",
            "ofm-sanga-delta-stage=openflexure_microscope.stage.sanga:SangaDeltaStage",
        ]
    },
    project_urls={
        "Source": "https://gitlab.com/openflexure/openflexure-microscope-server"
    },
)
