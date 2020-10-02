# OpenFlexure Microscope Software

## Quickstart

A general user-guide on setting up your microscope can be found [**here on our website**](https://www.openflexure.org/projects/microscope/).
This includes basic installation instructions suitable for most users.

Full developer documentation can be found on [**ReadTheDocs**](https://openflexure-microscope-software.readthedocs.io/). 
This includes installing the server in a mode better suited for active development.

## Developer installation

* `git clone https://gitlab.com/openflexure/openflexure-microscope-server.git`
* `poetry install`
* `poetry run build_static`

### Node installation

* Note, building the static interface will require a valid Node.js installation
* To build on a Raspberry Pi:
  * `curl -sL https://deb.nodesource.com/setup_14.x | sudo bash -`
  * `sudo apt install nodejs`

### Distributing

* `mkdir -p dist`
* `tar -c --exclude-vcs --exclude-from .tarignore -vzf dist/openflexure-microscope-server.tar.gz .`

#### Docker

We don't use docker to distribute the server application due to the number of system-level permissions it would need, and the fact that docker mounts break the autostorage extension. If you really want to use docker though, after building the image on your pi you need to start the container with the following flags:
* `docker run --privileged  -v /opt/vc:/opt/vc --env LD_LIBRARY_PATH=/opt/vc/lib --device /dev/vchiq --publish 5000:5000`

## Build-system

As of 1.0.0b0, we're using [Poetry](https://github.com/sdispater/poetry) to manage dependencies, build, and distribute the package. All package information and dependencies are found in `pyproject.toml`, in line with [PEP 518](https://www.python.org/dev/peps/pep-0518/). If you're developing this package, make use of `poetry.lock` to ensure you're using the latest locked dependency list.

## Microscope plugins

The Microscope module, and Flask app, both support plugins for extending lower-level functionality not well suited to web API calls. 
This plugin system is still in fairly early development, and is not yet properly documented. The current documentation can be found [here](https://openflexure-microscope-software.readthedocs.io/en/latest/plugins.html).

## Running tests through the PTVSD remote debugger (port 3000)

* From the openflexure-microscope-software directory, run `python3 -m ptvsd --host 0.0.0.0 --port 3000 --wait tests/test_camera.py`

## Credits

### Piexif

The microscope server includes a forked copy of hMatoba's [Piexif](https://github.com/hMatoba/Piexif), licensed under the MIT License.

### Video streaming

Based on supporting code for the article [video streaming with Flask](http://blog.miguelgrinberg.com/post/video-streaming-with-flask) and its follow-up [Flask Video Streaming Revisited](http://blog.miguelgrinberg.com/post/flask-video-streaming-revisited).
