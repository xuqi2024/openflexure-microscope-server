Thing Actions
=============

Introduction
------------

As well as properties, the OpenFlexure Microscope Server also supports Thing Actions. 
Thing Actions "invoke a function of the Thing, which manipulates state (e.g., toggling a lamp on or off) or triggers a process on the Thing (e.g., dim a lamp over time)." For the microscope, this would include moving the stage or taking a capture. Both of these require internal logic, and cannot be performed by changing a simple property.

Actions should be *triggered* with POST requests *only*. Ideally, a view corresponding to an action should only support POST requests.

Like properties, we use a special view class to identify a view as an action: ``ActionView``. For example, a view to perform a "quick-capture" action may look like:

.. code-block:: python

    class QuickCaptureAPI(ActionView):
        """
        Take an image capture and return it without saving
        """
        # Expect a "use_video_port" boolean, which defaults to True if none is given
        args = {"use_video_port": fields.Boolean(load_default=True)}

        # Our success response (200) returns an image (image/jpeg mimetype)
        responses = {
            200: {
                "content": { "image/jpeg": {} },
            }
        }

        def post(self, args):
            """
            Take a non-persistant image capture.
            """
            # Find our microscope component
            microscope = find_component("org.openflexure.microscope")

            # Open a BytesIO stream to be destroyed once request has returned
            with io.BytesIO() as stream:

                # Capture to our stream object
                microscope.camera.capture(stream, use_video_port=args.get("use_video_port"))

                # Rewind the stream
                stream.seek(0)

                # Return our image data using Flasks send_file function
                return send_file(io.BytesIO(stream.read()), mimetype="image/jpeg")

In this example, we are also making use of the ``responses`` attribute, to document that our successful response (HTTP code 200) will return data with a mimetype ``image/jpeg``, as well as ``args`` to accept optional parameters with POST requests.

Complete example
----------------

Adding this new view into our example extension, we now have:

.. literalinclude:: ./example_extension/05_actions.py
