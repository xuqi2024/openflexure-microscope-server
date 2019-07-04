OpenFlexure Microscope Software
=====================

# Quickstart

A general user-guide on setting up your microscope can be found [**here on our website**](https://www.openflexure.org/projects/microscope/).
This includes basic installation instructions suitable for most users.

Full developer documentation can be found on [**ReadTheDocs**](https://openflexure-microscope-software.readthedocs.io/en/stable/). 
This includes installing the server in a mode better suited for active development.

## Build-system
As of 1.0.0b0, we're using [Poetry](https://github.com/sdispater/poetry) to manage dependencies, build, and distribute the package. All package information and dependencies are found in `pyproject.toml`, in line with [PEP 518](https://www.python.org/dev/peps/pep-0518/). If you're developing this package, make use of `poetry.lock` to ensure you're using the latest locked dependency list.

## Microscope plugins
The Microscope module, and Flask app, both support plugins for extending lower-level functionality not well suited to web API calls. 
This plugin system is still in fairly early development, and is not yet properly documented. The current documentation can be found [here](https://openflexure-microscope-software.readthedocs.io/en/latest/plugins.html).

## Running tests through the PTVSD remote debugger (port 3000)
- From the openflexure-microscope-software directory, run `python3 -m ptvsd --host 0.0.0.0 --port 3000 --wait tests/test_camera.py`


# Credits
## Piexif
The microscope server includes a forked copy of hMatoba's [Piexif](https://github.com/hMatoba/Piexif), licensed under the MIT License.
## Video streaming
Based on supporting code for the article [video streaming with Flask](http://blog.miguelgrinberg.com/post/video-streaming-with-flask) and its follow-up [Flask Video Streaming Revisited](http://blog.miguelgrinberg.com/post/flask-video-streaming-revisited).
