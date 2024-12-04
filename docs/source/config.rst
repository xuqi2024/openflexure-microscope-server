Microscope settings
===================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. _MicroscopeRC:

Microscope settings file
------------------------

Microscope settings are made persistent via a microscope settings file. By default, this
file exists at ``/var/openflexure/settings/microscope_settings.json``.

The class :class:`openflexure_microscope.config.OpenflexureSettingsFile` provides functionality for loading a JSON-format settings file as a Python dictionary, and merging changed settings back into the file. 

The default settings are loaded by the :attr:`openflexure_microscope.config.user_settings`, which can be imported anywhere in the microscope server application to allow reading and writing of persistent settings.

.. automodule:: openflexure_microscope.config
    :members: