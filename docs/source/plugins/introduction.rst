Introduction
============

Plugins allow functionality to be added to the OpenFlexure Microscope without having to modify the base code.
They have full access to the :py:class:`openflexure_microscope.Microscope` object, 
including direct access to the attached :py:class:`openflexure_microscope.camera.pi.StreamingCamera` and :py:class:`openflexure_stage.stage.OpenFlexureStage` objects.
This also allows direct access to the :py:class:`picamera.PiCamera` object.

All microscope plugins must subclass :py:class:`openflexure_microscope.plugins.MicroscopePlugin` in order to be loaded by the microscopes :py:class:`openflexure_microscope.plugins.PluginMount`.

Once attached, all methods defined within the plugin class will be accessible from ``<microscope_object>.plugin.<plugin_namespace>.<plugin_method(args)>``.
Here, ``<microscope_object>`` is an instance of :py:class:`openflexure_microscope.Microscope`. The ``<plugin_method>`` is the method defined within your plugin class. Finally, ``<plugin_namespace>`` is determined differently depending on the type of plugin.

Plugins can either be loaded as a single Python file located anywhere on disk, or as a Python package installed to the environment being used. If loaded from a single file, the namespace is set to the file name (excluding .py extension) of the plugin file. If loaded from a package, the namespace is set to the name of the top-level module in the package. For example, if your plugin class definition resides within ``my_openflexure_plugins.microscope.mypluginpackage``, the namespace will be set to ``mypluginpackage``. Where possible, try to use descriptive, unique package names for this reason. For example, rather than name your plugin package ``autofocus``, which would like cause namespace clashes, instead name it ``yourname_autofocus``, or similar.

Module (single-file) plugins
----------------------------
For adding simple functionality, such as a few basic functions and API routes, a single Python file can be loaded as a plugin. 

This Python file must contain all of your plugin classes. Relative imports will not work. External modules and packages can be used with absolute imports, however for more complex plugins, it is often worth instead making use of an installable package plugin.

Package plugins
---------------
Generally, for adding anything other than very simple functionality, plugins should be written as `package distributions <https://packaging.python.org/tutorials/packaging-projects/>`_. This has the advantage of allowing relative imports, so functionality can be easily split over several files. For example, class definitions associated with API routes can be separated from class definitions associated with the microscope plugin.

The main restriction is that the plugin package must be importable using an absolute import from within the Python environment being used to load your microscope. 

Loading plugins with microscope_settings.yaml
---------------------------------------------
Both types of plugin are loaded by specifying the plugin class in your :ref:`MicroscopeRC`. In the case of a single-file plugin, specify the path to the plugin file, followed by the name of your :py:class:`openflexure_microscope.plugins.MicroscopePlugin` child class, separated by a colon. For packaged plugins, specify the absolute module name in place of the path.

For example, the plugins section of your microscope_settings.yaml file may look like:

.. code-block:: yaml

    ...
    plugins:
    - openflexure_microscope.plugins.default:Plugin
    - ~/my_plugins/my_plugin_file.py:MyPluginClass
    - my_openflexure_plugins.microscope.mypluginpackage:MyPluginClass
    ...
