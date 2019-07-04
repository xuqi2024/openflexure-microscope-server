Microscope configuration
========================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. _MicroscopeRC:

Microscope RC file
------------------

Microscope configuration is made persistent via a microscope runtime-config (RC) file. By default, this
file exists at ``~/.openflexure/microscope_settings.yaml``, and contains basic parameters to set up the microscope.

Additionally, by default, configurations for specific pieces of hardware (i.e. the stage and camera) are located
in separate "auxillary" config files, and are linked together by adding the config file's path to your main
microscope RC file. 


Loading the runtime-config
++++++++++++++++++++++++++

By default, a microscope object will load the a runtime-config from the default location.
This RC can then be passed to any hardware attached to the microscope. This can be particularly
useful when creating a dummy microscope object before attaching hardware. For example:

.. code-block:: python

    from openflexure_microscope import Microscope
    from openflexure_microscope.camera.pi import StreamingCamera
    from openflexure_stage import OpenFlexureStage

    # Create an empty microscope
    api_microscope = Microscope(None, None) 

    # Create a picamera StreamingCamera, using our config
    camera_obj = StreamingCamera(config=api_microscope.rc.read())

    # Create an OpenFlexure Stage attached to /dev/ttyUSB0
    stage_obj = OpenFlexureStage("/dev/ttyUSB0")  
    
    # Attach devices to the Microscope object
    api_microscope.attach(camera_obj, stage_obj)
    
Alternatively, a config can be loaded prior to creating a microscope, allowing the microscope
hardware to be created and attached in a single line. For example:

.. code-block:: python

    from openflexure_microscope.config import OpenflexureConfig

    from openflexure_microscope import Microscope
    from openflexure_microscope.camera.pi import StreamingCamera
    from openflexure_stage import OpenFlexureStage

    # Create a runtime-config from the default location
    rc = OpenflexureConfig(expand=True)

    # Create a populated microscope
    api_microscope = Microscope(
        StreamingCamera(config=rc), 
        OpenFlexureStage("/dev/ttyUSB0"),
        config=rc
    ) 


Config module and OpenflexureConfig class
-----------------------------------------
.. automodule:: openflexure_microscope.config
    :members: