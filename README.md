# OpenFlexure Microscope Software

> ## This is the v3 development branch
> We are no longer actively developing v2, but v3 is not yet released.
> v3 is not yet stable enough for wider public release. Development snapshots are released from time to time.
> If you want to use a development snapshot before we do a wider alpha release the best thing to do is get in contact on the [forum](https://openflexure.discourse.group/).
 If you want to look at the code for v2 you should look at the [master branch](https://gitlab.com/openflexure/openflexure-microscope-server/-/tree/master).


The "server" is the main component of the OpenFlexure Microscope's software.  It is responsible for controlling microscope hardware, data management, and allowing it to be controlled locally and over a network.
This repository includes the graphical interface, which is implemented as a web application served from the root of the Python web server. The simplest way to use it is via OpenFlexure eV, which should find your microscope on the network, and display the interface. The microscope's interface can also be accessed at `http://microscope.local:5000/` in a web browser, assuming the hostname of your microscope is `microscope`.

This software runs on [LabThings-FastAPI](https://github.com/labthings/labthings-fastapi/), which creates an HTTP server using FastAPI (which in turn relies on Starlette and pydantic).

## Getting started

A general user-guide on setting up your microscope can be found [**here on our website**](https://www.openflexure.org/projects/microscope/).
This includes basic installation instructions suitable for most users.
The simplest way to set up a microscope is to download the pre-built Raspberry Pi SD card image, which has this server already installed, along with all of its dependencies.
There are instructions on how to [use the microscope](https://openflexure.org/projects/microscope/control) once you have installed the software, either from OpenFlexure Connect, or through a web browser.
The web server starts on port 5000 by default, and the microscope SD image uses the hostname "microscope" so you can usually access the web interface at <http://microscope.local:5000/>.

A user guide and developer documentation **for v2 of the server** can be found on [**ReadTheDocs**](https://openflexure-microscope-software.readthedocs.io/), including some installation notes, a link to the HTTP API reference, and guidance for developing extensions.
More information is also available in the [handbook](https://gitlab.com/openflexure/microscope-handbook/), and in the "development instructions" below.

## Running directly

The Python package provides a command `ofm-microscope-server` that runs the server. This is what is used by `systemd` to run the service. You will need to provide some command-line arguments, see the output of `--help` for an up to date list. See `/etc/systemd/system/openflexure-microscope-server.service` for the command line used to run the server by default on the  Raspberry Pi. In general, you are likely to want to specify a configuration file with `-c`, a host (`--host 0.0.0.0` to serve on all addresses) and a port (`--port 5000`). The `--fallback` option will allow the server to start *even if the hardware specified in the configuration file can't load*. This serves an error page, rather than have the server fail. In the future, it should redirect users to a way to fix their configuration.

## Settings

The microscope is initially configured by a LabThings config file. This specifies two important things:

* The Python classes (and initialisation arguments) to use for each `Thing`. This sets the type of camera and stage, and enables/disables additional functionality like scanning and autofocus.
* The location of the settings folder, where each Thing can store its settings.

By default, this configuration file should be read from `/var/openflexure/settings/ofm_config.json` when the microscope is run as a service. If it is run at the command line you should specify the configuration using the `-c` command line flag. This configuration file does not change often, and usually only needs to be updated when you change the physical hardware. It may be that this file should be made read-only, particularly in microscopes deployed for e.g. medical applications.

The settings folder is, by default, `/var/openflexure/settings/` on the SD card, or `./settings/` if run elsewhere. It can be changed in the configuration file. This holds every other persistent setting. Camera settings, calibration data, default capture settings, stream resolution and so on. There is one folder per `Thing`, each with their own file. The settings files can change very regularly, and if you need to reset your settings, it's usually these files that you should remove or reset. If you delete one settings file this should reset the corresponding `Thing`, you don't have to delete the whole folder.

# Developer guidelines

## Developing on a Raspberry Pi

The easiest way to work on the software is to build an OpenFlexure Microscope around a Raspberry Pi, using our custom disk image.  This includes a pre-installed copy of this server, and a pre-built copy of the web application, so it's ready to use.  You can also develop directly on the Raspberry Pi, and this is the best way to test out changes to the Python code using actual hardware.  

You can manage the server with the `ofm` command, using `ofm start`, `ofm stop`, and `ofm restart` to do the respective actions. Often, stopping the server and running it manually will make errors easier to spot. To do this, run:
```
ofm stop
ofm activate
cd /var/openflexure
sudo -u openflexure-ws openflexure-microscope-server -c microscope_configuration.json --host 0.0.0.0 --port 5000
```

Our favourite way of working with the server on a Pi is to follow the instructions above, then open a VSCode Remote session from another computer.  This allows you to use your usual developer environment to write code, but everything runs on the Raspberry Pi with real hardware.  Note that the repository is cloned by default over `https`, so you will probably need to change the "remote" URL to your fork of the repository, or to SSH, before you're able to push changes.

### Updating just the web app

Installing and running node.js on a Raspberry Pi is slow and often frustrating.  Our preference is to do node.js development on another computer, and connect either to a dummy server on that computer, or to a real microscope elsewhere on the network.  If you only want to work on the Python code, it's possible to download a pre-built web application and use it with your modified Python code.  To do this, locate the archive of the web application, and then run:
```
cd /var/openflexure/
sudo chown -R openflexure-ws.openflexure-ws .
sudo chmod -R g+w .
cd application/openflexure-microscope-server/
sudo rm -rf openflexure_microscope/api/static/dist/
curl <tarball URL> | tar -xz
```
NB the `sudo chown` and `sudo chmod` lines are probably unnecessary, but depending on the state of your system they may fix annoying permissions issues.

To find the `<tarball URL>` you should look for `openflexure-microscope-webapp-<version>.tar.gz` on the [build server](https://build.openflexure.org/openflexure-microscope-server/), or open the `package` job of a CI pipeline on this repository, and locate it by browsing the artifacts.  That should work for any merge request that's currently open.

## Installation on other platforms

The Raspberry Pi image we use currently ships with Python 3.7.3. For local development on a different platform, please use PyEnv or similar to make sure you're running on this version. For example, Windows users can use [Scoop](https://scoop.sh/) to install specific Python versions.  This repository contains two closely related parts; a web server written in Python, that handles hardware control, and a web application using Vue.js that provides a graphical control interface.  It is possible to work on either of these in isolation, but bear in mind that if you only set up Python development, you will need to host the web application elsewhere.

Most of our core team don't run the Javascript development on the Raspberry Pi, as npm can be quite slow to build the application.  Instead, we set up the Python part of the project on a Raspberry Pi, and run the Javascript part on your development machine.  You can then connect to the web application served from your local machine, and enter the address of the Raspberry Pi when the interface first loads.

To set up a development version of the software (most likely using emulated camera and stage if you're not running on a Raspberry Pi):

### Clone the repository
* `git clone https://gitlab.com/openflexure/openflexure-microscope-server.git`
* `cd openflexure-microscope-server`

### Set up the Python environment and run a test server
* (Optional) Set local Python version to 3.11
* Create a virtual environment and activate it:
  * `python -m venv .venv`
  * `source .venv/bin/activate` (on Linux) or `.venv/Scripts/activate` (on Windows)
  * `pip install -e .[dev]` (This will install development dependencies.  If you don't need these, there is probably a simpler way to run the server than cloning this repo.)
* Finally, run the server: currently you can do this with `sudo systemctl start openflexure-microscope-server` if it's pre-installed on a Raspberry Pi, or `openflexure-microscope-server -c ofm_config_stub.json` to run locally.

### Run the server manually on a Raspberry Pi
```
cd /var/openflexure
sudo -u openflexure-ws PATH="/var/openflexure/application/openflexure-microscope-server/.venv/bin/:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin" /var/openflexure/application/openflexure-microscope-server/.venv/bin/openflexure-microscope-serve -c /var/openflexure/settings/ofm_config.json --host 0.0.0.0 --port 5000
```


### Set up the Javascript environment and build

The Labthings-FastAPI server, written in Python, serves a web application written in `Vue.js` (Vue2).  This is distributed with the SD card image for the microscope.

For more details on the web app see the ReadMe in the [webapp](./webapp) directory.


## Formatting, linting, and tests
All of the commands below assume that you are running in the OFM virtual environment, i.e. you have run `ofm activate` on an OpenFlexure SD card, or `source .venv/bin/activate` on Linux, or `.venv/Scripts/activate`on Windows.

**Before committing** you should lint and auto-format your code:

* To lint run `ruff check`
* To auto-format the Python code run `ruff format`
* To auto-format the Javascript code, run
  * `cd webapp`
  * `npm run lint`

**Before merging** please auto-format your code and also run the quality checks (linting, static analysis, and unit tests)

* All commands above
* `mypy src` (currently fails)
* `pytest`


### Details

We use several code analysis and formatting libraries in this project. Our CI will check each of these automatically, so ensuring they pass locally will save you time. Currently `ruff` is used for linting/formatting and `pytest` for unit tests. `mypy` will be enabled once the codebase is ready.

## Python environment, build, and dependencies

As of `v3` we specify dependencies in `pyproject.toml`. These are not currently frozen due to difficulties matching versions on different platforms. On Raspberry Pi, it's best to specify `--only-binary=:all:` to ensure libraries like `numpy` and `scipy` are not compiled from source (which takes many hours, and/or fails). Pinning dependencies with `requirements.txt` and/or `requirements.in` may happen in the future.

## Creating releases

* Update the application's internal version number
  * Edit `pyproject.toml` to update the version number
* Update the changelog
* Git commit and git push
* Create a new version tag on GitLab (e.g. `v2.6.11`) that matches the `pyproject.toml` version number.
    * Make sure you prefix a lower case 'v', otherwise it won't be recognised as a release!
    * This tagging will trigger a CI pipeline that builds the JS client, tarballs up the server, and deploys it
        * Note: This also updates the build server's nginx redirect map file

## Changelog generation

* `npm install -g conventional-changelog-cli`
* `npx conventional-changelog -r 1 --config ./changelog.config.js -i CHANGELOG.md -s`

## Adding functionality

The microscope comprises a number of `Thing` instances, which provide actions and properties to implement hardware control and software features. These may be imported from any Python module, using `ofm_config.json`. See the LabThings-FastAPI documentation for how to create a `Thing`. 

Currently, the camera and stage classes are provided by external libraries, `labthings-picamera2` and `labthings-sangaboard`. Replacing these is the easiest way to use alternative hardware: interfaces are defined in `openflexure_microscope_server.things.camera` and `openflexure_microscope_server.things.stage` respectively.
