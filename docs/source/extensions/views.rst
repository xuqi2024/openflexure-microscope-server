Adding web API views
====================

Introduction
------------
Extensions can create views to expose extension functionality via the web API. Creating API views for your extension is strongly recommended, as this is the primary way we encourage interaction with the microscope device.

As with most HTTP APIs, we make use of basic HTTP request methods. GET requests return data without modifying any state. POST requests completely replace data with data passed as request arguments. PUT requests update data with new data passed as request arguments. DELETE requests delete a particular object from the server. Your API views need not implement all of these methods.

Continuing our example on the previous page, and discussed below, adding API views may look like:

.. literalinclude:: ./example_extension/02_adding_views.py

Note that we are now passing our microscope object as an argument to our API methods. Finding the microscope component is performed by the API view at request-time, and passed onto the functions.

In this case, our extension will have two new API views at `/identify` and `/rename`. The `/identify` view only accepts GET requests, and the `/rename` view only accepts POST requests.

Request arguments
+++++++++++++++++

For POST and PUT requests, data usually needs to be provided to the view in order to perform its function. In this example, our ``rename`` view requires a new microscope name to be passed. We make use of the ``@use_body`` decorator to provide this functionality.

``@use_body`` defines the type of data expected in the request body. In this example, we use ``String`` type data. The arguments of ``fields.String`` allow us to provide additional information, such as the parameter being required, and example values to appear in API documentation.

Adding additional fields, and the meaning of the field types, will be discussed further in the next section.

When a POST request is made to our API view, the ``@use_body`` converts the body of the request into a ``String``, and passes it as a positional argument to our ``post`` function.

Swagger documentation
+++++++++++++++++++++

At this point, it is useful to introduce the automatically generated Swagger documentation. From any web browser, go to ``http://microscope.local/api/v2/swagger-ui`` (or replace ``microscope.local`` with your microscope's IP address if ``microscope.local`` doesn't work for your system).

This page uses `SwaggerUI <https://swagger.io/tools/swagger-ui/>`_ to provide visual, interactive API documentation. Find your extensions URL in the documentation under the ``extensions`` group. Basic documentation about the parameters required for your POST method should be visible, as well as an interactive example filled out with the example request given in ``@use_body``.
