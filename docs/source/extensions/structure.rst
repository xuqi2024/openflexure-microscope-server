Basic extension structure
=========================

An extension starts as a simple instance of :py:class:`labthings.server.extensions.BaseExtension`. 
Each extension is described by a single ``BaseExtension`` instance, containing any number of methods, API views, and additional hardware components. 

In order to access the currently running microscope object, use the :py:func:`labthings.server.find.find_component` function, with the argument ``"org.openflexure.microscope"``. Likewise, any new components attached by other extensions can be found using their full name, as above.

A simple extension file, with no API views but application-available methods may look like:

.. literalinclude:: ./example_extension/01_basic_structure.py


Once this extension is loaded, any other extensions will have access to your methods:

.. code-block:: python

    from labthings.server.find import find_extension

    def test_extension_method():
        # Find your extension. Returns None if it hasn't been found.
        my_found_extension = find_extension("com.myname.myextension")

        # Call a function from your extension
        if my_found_extension:
            my_found_extension.identify()


Subclassing ``BaseExtension``
-------------------------------

The syntax used above allows novice programmers to easily start building extensions, without having to deal with subclassing. However, for more complex extensions which require persistent state, subclassing :py:class:`labthings.server.extensions.BaseExtension` is recommended.

The same simple extension as seen above can be written using subclassing:

.. literalinclude:: ./example_extension/01b_basic_structure_subclass.py
