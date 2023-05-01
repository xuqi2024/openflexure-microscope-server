# OpenFlexure Microscope Software

## PICAMERA2 DEVELOPMENT BRANCH

This is an early-stage attempt at supporting newer cameras using the picamera2 interface.

### Current status:
 - [x] MJPEG stream
 - [x] Capturing images
 - [x] Raw captures to dng
 - [ ] Recording videos (implemented but not tested)
 - [ ] Direct rendered preview
 - [ ] Camera configuration
 - [ ] Automatic calibration
 - [ ] Lens shading
 - [ ] Fast autofocus (probably)
 - [ ] Building the venv
 - [ ] Switching between picamera and picamera2

There's likely more things broken, the main goal was to get an idea of the complexity involved in supporting new cameras.

## OpenFlexure Microscope Server

The "server" is the main component of the OpenFlexure Microscope's software.  It is responsible for controlling microscope hardware, data management, and allowing it to be controlled locally and over a network.
This repository now includes the web client, which is served from the root of the Python web server.
This software runs on [Python-LabThings](https://github.com/labthings/python-labthings/), and so most non-microscope functionality is handled by that library.

## Getting started

A general user-guide on setting up your microscope can be found [**here on our website**](https://www.openflexure.org/projects/microscope/).
This includes basic installation instructions suitable for most users.
The simplest way to set up a microscope is to download the pre-built Raspberry Pi SD card image, which has this server already installed, along with all of its dependencies.
There are instructions on how to [use the microscope](https://openflexure.org/projects/microscope/control) once you have installed the software, either from OpenFlexure Connect, or through a web browser.
The web server starts on port 5000 by default, and the microscope SD image uses the hostname "microscope" so you can usually access the web interface at <http://microscope.local:5000/>.

A user guide and developer documentation can be found on [**ReadTheDocs**](https://openflexure-microscope-software.readthedocs.io/), including some installation notes, a link to the HTTP API reference, and guidance for developing extensions.
More information is also available in the [handbook](https://gitlab.com/openflexure/microscope-handbook/), and in the "development instructions" below.

## Settings

There are 2 important settings files, described in the [docs](https://openflexure-microscope-software.readthedocs.io/en/master/config.html).  The paths given below are for the Raspberry Pi installation on our pre-built SD card, and will change if you run on another system:
* `/var/openflexure/settings/microscope_configuration.json`
    * Boot-time microscope configuration. Things like the type of camera connected, the stage board, geometry etc.
    * Anything that needs to be loaded once as the server starts, and usually doesn't need to be re-written while the server is running
    * This configuration file does not change often, and usually only needs to be updated when you change the physical hardware.
* `/var/openflexure/settings/microscope_settings.json`
    * Every other persistent setting. Camera settings, calibration data, default capture settings, stream resolution etc.
    * This file changes very regularly, and if you need to reset your settings, it's usually this file that you should remove or reset.

# Developer guidelines

## Developing on a Raspberry Pi

The easiest way to work on the software is to build an OpenFlexure Microscope around a Raspberry Pi, using our custom disk image.  This includes a pre-installed copy of this server, and a pre-built copy of the web application, so it's ready to use.  You can also develop directly on the Raspberry Pi, and this is the best way to test out changes to the Python code using actual hardware.  To do this, use the command-line script `ofm develop`.  This will replace the server application at `/var/openflexure/application/openflexure-microscope-server/` with a clone of this git repository.  You can manage the server with the `ofm` command, using `ofm start`, `ofm stop`, and `ofm restart` to do the respective actions. `ofm serve` will run a debug server that prints its logs and errors to the console.

Our favourite way of working with the server on a Pi is to follow the instructions above, then open a VSCode Remote session from another computer.  This allows you to use your usual developer environment to write code, but everything runs on the Raspberry Pi with real hardware.  Note that `ofm develop` uses an `https://` address for the git repository, so you will probably need to change the "remote" URL to your fork of the repository, or to SSH, before you're able to push changes.

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
* (Optional) Set local Python version to match what is available on the Pi
  * `pyenv init` (this may or may not be required, depending on how you installed `pyenv`)
  * `pyenv install 3.7.3`
  * `pyenv local 3.7.3`
* Create a virtual environment and activate it:
  * `python -m venv .venv`
  * `source .venv/bin/activate` (on Linux) or `.venv/Scripts/activate` (on Windows)
  * `pip install --upgrade pip wheel pipenv`
  * `pipenv install --dev` (This will install development dependencies.  If you don't need these, `pipenv install` will get you just the dependencies needed to run the server, which takes about half the time.)
* Finally, run the server:
  * You can use `ofm serve` or `ofm restart` on the Raspberry Pi to manage the server.
  * To run the server locally, with dummy hardware, you can use `python -m openflexure_microscope.api.app` to start a development-mode Flask server on `localhost:5000`

### Set up the Javascript environment and build
* The Flask web application, written in Python, serves a web application written in `Vue.js`.  This is distributed as part of the built version of the server, hosted on our [build server](https://build.openflexure.org/openflexure-microscope-server/).
* You could extract the pre-built web app from this tarball, which saves you having to set up Node.js.  However, it also means you're not able to change the interface, and it's possible your interface will get out of sync with your server.
* Building the web interface will require a valid Node.js installation.  If you don't have Node.js (including `npm`) the [Node.js website](https://nodejs.org/en/) offers downloads for all platforms, though see the instructions below for Raspberry Pi.
  * To install Node.js on a Raspberry Pi:
    * `curl -sL https://deb.nodesource.com/setup_14.x | sudo bash -`
    * `sudo apt install nodejs`
* To build the web application (this produces a set of static files, that are served by the Flask webserver)
  * `cd webapp`
  * `npm install`
  * `npm run build`
* To create a Node.js development server (this will help various development tools to display more information, and auto-rebuilds when you change the source files)
  * `npm run serve`
  * You access the development server on a different port (it's printed on the command line when you run the above command).  This means that when it starts up you will need to tell it where the microscope server is, using the "override API origin" field in the page that pops up.  If you are running a test server on your computer, this is most likely `http://localhost:5000/`.

## Formatting, linting, and tests
All of the commands below assume that you are running in the OFM virtual environment, i.e. you have run `ofm activate` on an OpenFlexure SD card, or `source .venv/bin/activate` on Linux, or `.venv/Scripts/activate`on Windows.

**Before committing** you should auto-format your code:

* To auto-format the Python code run `poe format`
* To auto-format the Javascript code, run
  * `cd webapp`
  * `npm run lint`

**Before submitting a merge request/merging** please auto-format your code and also run the quality checks (linting, static analysis, and unit tests)

* To auto-format and type-check the Python code run `poe check`
* To auto-format the Javascript code, run
  * `cd webapp`
  * `npm run lint`


### Details

We use several code analysis and formatting libraries in this project. **Please run all of these before submitting a merge request.**

Our CI will check each of these automatically, so ensuring they pass locally will save you time.

* **Black** - Code formatting with minimal configuration.
  * While sometimes it's not perfect, its fine 90% of the time and prevents arguments about formatting.
  * Automatically formats your code
  * This will rewrite your files in-place, so if you want to be able to revert, make a backup first!
  * `poe black`
* **Pylint** - Static code analysis
  * Analyses your code, failing if issues are detected.
  * We've disabled some less severe warnings, so _if anything fails your merge request will be blocked_
  * `poe pylint`
* **Mypy** - Type checking
  * Analyses your type hints and annotations to flag up potential bugs
  * Where possible, use type hints in your code. Even if dependencies don't support it, it'll help identify issues.
  * `poe mypy`
* **Pytest** - Unit testing
  * While unit testing is of limited use due to our dependence on real hardware, some simple isolated functions can (and should) be unit tested.
  * `poe test`

Though not in the CI, our `format` script also runs isort:

* **Isort** - Import sorting
  * Automatically organises your imports to stop things getting out of hand
  * `poe isort`

## Python environment, build, and dependencies

As of `2.10.0b0` we have switched to using `pipenv` for managing dependencies, and a standard `setuptools` based build system.  See "local installation" above for instructions on how to install the project.  Earlier versions of the project used `poetry` but we moved away because of [difficulties](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/124) getting it to work both on the Raspberry Pi and in our CI pipeline.  The new arrangement for configuration files is:

* Dependencies, and dev-dependencies, are specified in `setup.py` in the usual way (using `install_requires` and `extra_requires[dev]`).
* Package metadata is specified in `setup.py` in the usual way.
* `pyproject.toml` is retained, but *no longer includes package metadata or dependencies* and does not have a `[tool.poetry]` table.  It does define the build system as per PEP517, which is `setuptools`, and it also contains settings for `black`, `poe` and `isort`.
* `Pipfile` is very minimal, and only declares dependencies on the current module, i.e. the dependencies declared in `setup.py`.  It also specifies the Python version.  This allows us to single-source dependency information from `setup.py` but use the dependency resolution/locking functionality of `pipenv`
* `Pipfile.lock` locks the dependency versions in the same way as `poetry.lock` used to, i.e. it specifies exact versions of everything, derived from the looser specifications in `setup.py`.
* Dependency resolution is a pain, in part because compiling packages like scipy and numpy from source on a Pi is slow and unreliable. To avoid this, we usually lock the dependencies on a Raspberry Pi, using:
  `PIP_ONLY_BINARY="numpy, scipy, matplotlib" pipenv lock --dev`
  This forces the use of wheels only, and thus restricts us to things that built OK on Piwheels.  The resulting Pipfile.lock should then work nicely on other Raspberry Pis.
* **The Pipfile we use is now Raspberry Pi-specific** so if you attempt to use it on other platforms it will probably fail. This is because we've removed `pypi` to avoid hash conflicts. The CI now runs on a Raspberry Pi image, so that the tests use a similar environment to our deployment.  Currently, changing the `[source]` entry back to PyPi will allow you to re-lock the dependencies on other platforms. In the future we may need to maintain two Pipfiles and two Pipfile.lock files.

## Creating releases

* Update the application's internal version number
    * Edit `setup.py` to update the version number
    * Git commit and git push
* Create a new version tag on GitLab (e.g. `v2.6.11`)
    * Make sure you prefix a lower case 'v', otherwise it won't be recognised as a release!
    * This tagging will trigger a CI pipeline that builds the JS client, tarballs up the server, and deploys it
        * Note: This also updates the build server's nginx redirect map file

## Changelog generation

* `npm install -g conventional-changelog-cli`
* `npx conventional-changelog -r 1 --config ./changelog.config.js -i CHANGELOG.md -s`

## Microscope extensions

The Microscope module, and Flask app, both support plugins for extending lower-level functionality not well suited to web API calls. The current documentation can be found [here](https://openflexure-microscope-software.readthedocs.io/en/latest/plugins.html).
If you want to add functions to the microscope software, this is probably the best mechanism to use if it works for you.


```
