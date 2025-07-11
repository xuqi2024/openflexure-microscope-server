"""The OpenFlexure Microscope Server Package.

The OpenFlexure Microscope Server is a LabThings-FastAPI server. All hardware
interfaces, and almost all functionality exposed over HTTP is done using ``Things``.

On the microscope the server is started by systemd. It can be controlled using commands
such as ``ofm restart``, ``ofm start``, and ``ofm stop``.

The server can also be run in simulation mode from the terminal. In the root directory
of the repository the server can be started with run:

.. code-block:: bash

    openflexure-microscope-server --fallback -c ./ofm_config_simulation.json


"""
