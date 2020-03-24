Lifecycle Hooks
===============

Introduction
------------
In some cases it is useful to have functions triggered by events in an extensions lifecycle. Currently two such lifecycle events can be used, ``on_register``, and ``on_component``.

``on_register``
---------------

The ``on_register`` method can be used to have a function call as soon as the extension has been successfully registered to the microscope. For example:

.. code-block:: python

    class MyExtension(BaseExtension):
        def __init__(self):

            # Track if the extension has been registered
            self.registered = False

            # Add lifecycle hooks
            self.on_register(self.on_register_handler, args=(), kwargs={})

            # Superclass init function
            super().__init__("com.myname.myextension", version="0.0.0")

        def on_register_handler(self, *args, **kwargs):
            self.registered = True
            print("Extension has been registered!")


``on_component``
----------------

The ``on_component`` method can be used to have a function call as soon as a particular LabThings component has been added. This can be used, for example, to get information about the microscope instance as soon as it is available. For example:

.. code-block:: python

    class MyExtension(BaseExtension):
        def __init__(self):

            # Hold a reference to the microscope object as soon as it is available
            self.microscope = None

            # Add lifecycle hooks
            self.on_component("com.myname.myextension", self.on_microscope_handler)

            # Superclass init function
            super().__init__("org.openflexure.microscope", version="0.0.0")

        def on_microscope_handler(self, microscope_object):
            print("Microscope object has been found!")
            self.microscope = microscope_object