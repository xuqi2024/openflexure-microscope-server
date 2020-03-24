Introduction
============

Extensions allow functionality to be added to the OpenFlexure Microscope web API without having to modify the base code.
They have full access to the :py:class:`openflexure_microscope.Microscope` object, 
including direct access to any attached :py:class:`openflexure_microscope.camera.base.BaseCamera` and :py:class:`openflexure_stage.stage.OpenFlexureStage` objects.
This also allows access to the :py:class:`picamera.PiCamera` object.

Extensions can either be loaded from a single Python file, or as a Python package installed to the environment being used. 

Single-file extensions
----------------------
For adding simple functionality, such as a few basic functions and API routes, a single Python file can be loaded as a extension. This Python file must contain all of your extension objects, and be located in the applications extensions directory (by default ``~/.openflexure/microscope_extensions``).

Package extensions
------------------
Generally, for adding anything other than very simple functionality, extensions should be written as `package distributions <https://packaging.python.org/tutorials/packaging-projects/>`_. This has the advantage of allowing relative imports, so functionality can be easily split over several files. For example, class definitions associated with API routes can be separated from class definitions associated with the microscope extension.

The main restriction is that the extension package must be importable using an absolute import from within the Python environment being used to load your microscope. 

In order to enable your packaged extension, create a file in the applications extensions directory (by default ``~/.openflexure/microscope_extensions``) which imports your extension object(s) from your module.
