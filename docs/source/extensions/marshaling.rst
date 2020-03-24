Marshaling data
===============

Introduction
------------

The OpenFlexure Microscope Server makes use of the `Marshmallow library <https://github.com/marshmallow-code/marshmallow/>`_ for both response and argument marshaling. From the Marshmallow documentation:

    **marshmallow** is an ORM/ODM/framework-agnostic library for converting complex datatypes, such as objects, to and from native Python datatypes.

    In short, marshmallow schemas can be used to:

    - **Validate** input data.
    - **Deserialize** input data to app-level objects.
    - **Serialize** app-level objects to primitive Python types. The serialized objects can then be rendered to standard formats such as JSON for use in an HTTP API.

When developing extensions, you are encouraged to make use of the ``@marshal_with`` and ``@use_args`` decorators, along with schemas, to handle serialisation of your API responses, and parsing of request parameters respectively.

Schemas and fields
++++++++++++++++++

A **field** describes the data type of a single parameter, as well as any other properties of that parameter for use in parsing, and documentation. For example, a String-type field, with a default value in case no actual value is passed, and extra documentation, may look like:

.. code-block:: python

    fields.String(required=False, missing="Default value", example="Example value")

A **schema** is a collection of keys and fields describing how an object should be serialized/deserialized. Schemas can be created in several ways, either by creating a ``Schema`` class, or by passing a dictionary of key-field pairs. Both methods will be discussed in the following examples.


Argument parsing
++++++++++++++++

In the previous section we saw how to use fields and ``@use_body`` to get simple arguments from requests, in which a single parameter is required. By making use of Marshmallow schemas, and the `Webargs library <https://github.com/marshmallow-code/webargs>`_, we can allow for more complex requests containing many parameters of different types. The parsed request parameters are then passed to the view function as a positional argument (as before), in the form of a dictionary. 

For example, if you are creating an API route, in which you expect parameters ``name``, ``age``, and optionally, ``job``, your schema class may look like:

.. code-block:: python

    from labthings.server.schema import Schema
    from labthings.server import fields

    class UserSchema(Schema):
        name = fields.String(required=True)
        age = fields.Integer(required=True)
        job = fields.String(required=False, missing="Unknown")

To inform your POST method to expect these arguments, use the ``@use_args`` decorator:

.. code-block:: python

    @use_args(UserSchema())
    def post(self, args):
        ..

Alternatively, if your schema is only used in a single location, it may be simpler to create a dictionary schema only where it is used, for example:

.. code-block:: python

    @use_args({
        "name": fields.String(required=True),
        "age": fields.Integer(required=True),
        "job": fields.String(required=False, missing="Unknown")
    })
    def post(self, args):
        ...

A compatible request body, in JSON format, may look like:

.. code-block:: json

    {
        "name": "John Doe",
        "age": 45,
        "job": "Python developer"
    }


This JSON data is the parsed, converted into a Python dictionary, and passed as an argument. Retreiving the data from within your view function may therefore look like:

.. code-block:: python

    @use_args({
        "name": fields.String(required=True),
        "age": fields.Integer(required=True),
        "job": fields.String(required=False, missing="Unknown")
    })
    def post(self, args):
        name = args.get("name")  # Returns "John Doe", type str
        age = args.get("age")  # Returns 45, type int
        job = args.get("job")  # Returns "Python developer", type str


Object serialization
++++++++++++++++++++

Schemas can also be used to format our data so that it is suitable for an API response. Our API expects JSON formatted data both in, and out. It is therefore important that your API views respond with valid JSON where possible. 

Continuing with our example in the previous pages, we will enhance our ``identify`` method to provide more, better formatted information about our current microscope.

We start by creating a schema to describe how to serialise a :py:class:`openflexure_microscope.Microscope` object.

.. code-block:: python

    # Define which properties of a Microscope object we care about,
    # and what types they should be converted to
    class MicroscopeIdentifySchema(Schema):
        name = fields.String()  # Microscopes name
        id = fields.UUID()  # Microscopes unique ID
        state = fields.Dict()  # Status dictionary
        camera = fields.String()  # Camera object (represented as a string)
        stage = fields.String()  # Stage object (represented as a string)


We use this new schema in our ``identify`` view like so:

.. code-block:: python

    class ExampleIdentifyView(View):
        # Format our returned object using MicroscopeIdentifySchema
        @marshal_with(MicroscopeIdentifySchema())
        def get(self):
            # Find our microscope component
            microscope = find_component("org.openflexure.microscope")

            # Return our microscope object,
            # let @marshal_with handle formatting the output
            return microscope

Note that our ``get`` method now returns the :py:class:`openflexure_microscope.Microscope` object itself. No formatting is done by the function, it is entirely handled by ``@marshal_with(MicroscopeIdentifySchema())``. Additionally, since we defined our schema as a class, it can be re-used elsewhere.

For our ``rename`` view, we will use a simpler schema for our input arguments, defined by a dictionary (since we are only expecting a single parameter in, and it will likely not be re-used elsewhere). Our response, however, will use our ``MicroscopeIdentifySchema`` class. This means that the *response* of our ``identify`` and ``rename`` views will be identically formatted.

Our ``rename`` view class may now look like:

.. code-block:: python

    class ExampleRenameView(View):
        # Format our returned object using MicroscopeIdentifySchema
        @marshal_with(MicroscopeIdentifySchema())
        # Expect a request parameter called "name", which is a string. Pass to argument "args".
        @use_args({"name": fields.String(required=True, example="My Example Microscope")})
        def post(self, args):
            # Look for our "name" parameter in the request arguments
            new_name = args.get("name")

            # Find our microscope component
            microscope = find_component("org.openflexure.microscope")

            # Pass microscope and new name to our rename function
            rename(microscope, new_name)

            # Return our microscope object,
            # let @marshal_with handle formatting the output
            return microscope


Complete example
++++++++++++++++

Combining both of these into our example extension, we now have:

.. literalinclude:: ./example_extension/03_marshaling_data.py