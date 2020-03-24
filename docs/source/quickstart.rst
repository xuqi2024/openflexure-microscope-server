Quickstart
=======================================================

Install
-------

Stable installation
+++++++++++++++++++
For most users, the OpenFlexure Microscope software should be installed using our `pre-built Raspbian SD card image. <https://openflexure.org/projects/microscope/install>`_


Manual installation
+++++++++++++++++++

For offline (i.e. no real microscope connected) development, a basic development server can run on any system.

- (Recommended) create and activate a virtual environment
- Install non-python dependencies with ``sudo apt-get install libatlas-base-dev libjasper-dev libjpeg-dev``
- Install `Poetry <https://github.com/sdispater/poetry>`_, clone this repo, and ``poetry install`` from inside the repo.

Managing the server
-------------------

Managing the server through the installer script's CLI is documented `on our website <https://openflexure.org/projects/microscope/install#managing-the-microscope-server>`_.

This includes starting the server as a background service, as well as starting a development server with real-time debug logging.