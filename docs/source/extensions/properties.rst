Thing Properties
================

Introduction
------------

As well as generating Swagger documentation, the server will generate a draft `W3C Thing Description <https://www.w3.org/TR/wot-thing-description/>`_ . This description allows the microscope's features to be understood in a common "Web of Things" language.

Thing Properties "expose state of the Thing. This state can then be retrieved (read) and optionally updated (write)." For the microscope, this includes the current read-only state, such as if the microscope has real camera or stage hardware attached, as well as read-write states like camera settings, and the microscope name. 

The property description for a view will be generated automatically from your available view methods, any schema decorators used, and any docstrings added to the view.


Defining Thing Properties
-------------------------

In order to register a view as a Thing property, we use the ``PropertyView`` class, like so:

.. code-block:: python

    # Since we only have a GET method here, it'll register as a read-only property
    class ExampleIdentifyView(PropertyView):
        # Format our returned object using MicroscopeIdentifySchema
        schema = MicroscopeIdentifySchema()

        def get(self):
            """
            Show identifying information about the current microscope object
            """
            # Find our microscope component
            microscope = find_component("org.openflexure.microscope")

            # Return our microscope object,
            # let schemah handle formatting the output
            return microscope


Property schema
---------------

For read-write properties, it is best practice for the expected request arguments, and the views responses, to follow the same format. In this way, by looking at the response of a GET request, one can know the type of data expected in by a PUT request. 

For example, if your GET request returns the JSON:

.. code-block:: json

    {
        "name": "John Doe",
        "age": 45,
        "job": "Python developer"
    }

and your property supports PUT requests (for updating data), then a valid PUT request could contain the data:

.. code-block:: json

    {
        "age": 46,
        "job": "Landscape gardener"
    }

This request would update the property, such that a GET request would *now* return:

.. code-block:: json

    {
        "name": "John Doe",
        "age": 46,
        "job": "Landscape gardener"
    }

In Property Views the ``schema`` class attribute acts as the schema for both marshalling responses *and* parsing arguments. This is because property requests and responses should be identically formatted.

We will implement the ``schema`` attribute in our ``ExampleRenameView`` view from our previous example:

.. code-block:: python

    # We can use a single schema as the input and output will be formatted identically
    # Eg. We always expect a "name" string argument, and always return a "name" string attribute
    class ExampleRenameView(PropertyView):
        schema = {"name": fields.String(required=True, metadata={"example": "My Example Microscope"})}
    
        def get(self):
            """
            Show the current microscope name
            """
            # Find our microscope component
            microscope = find_component("org.openflexure.microscope")

            return microscope

        def post(self, args):
            """
            Change the current microscope name
            """
            # Look for our "name" parameter in the request arguments
            new_name = args.get("name")

            # Find our microscope component
            microscope = find_component("org.openflexure.microscope")

            # Pass microscope and new name to our rename function
            rename(microscope, new_name)

            # Return our microscope object,
            # let schema handle formatting the output
            return microscope

Complete example
----------------

Combining these into our example extension, we now have:

.. literalinclude:: ./example_extension/04_properties.py
