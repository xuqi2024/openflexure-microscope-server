Quickstart
=======================================================

Install
-------

Stable installation
+++++++++++++++
For most users, this is the reccommended installation method.

- Run ``curl -LSs get.openflexure.org/microscope |sudo bash``
    - See the `GitLab repo <https://gitlab.com/openflexure/openflexure-microscope-cli>`_ for details.
- Follow on-screen prompts

Developer and non-interactive installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The installer script can pull the latest development package from our git repository, and use install into a developer environment using Poetry. 
Options also exist to run the installer without any user prompts.

See the `installer script GitLab repo <https://gitlab.com/openflexure/openflexure-microscope-cli>`_ for details.

Manual installation
+++++++++++++++++++
- (Recommended) create and activate a virtual environment
- Install non-python dependencies with ``sudo apt-get install libatlas-base-dev libjasper-dev libjpeg-dev``
- Install `Poetry <https://github.com/sdispater/poetry>`_, clone this repo, and ``poetry install`` from inside the repo.

Managing the server
-------------------

Managing the server through the installer script's CLI is documented `on our website <https://openflexure.gitlab.io/projects/microscope/#managing-the-microscope-server>`_.

This includes starting the server as a background service, as well as starting a development server with real-time debug logging.