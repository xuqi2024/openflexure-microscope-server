Example plugin
--------------

plugin.py
+++++++++

.. literalinclude:: example/plugin.py
  :language: python

schema.json
+++++++++++

.. literalinclude:: example/schema.json
  :language: JSON

Notes
+++++

In this example, if the package or file were named ``my_plugin``, the three microscope plugin methods would be accessible from ``<microscope_object>.plugin.my_plugin.identify()``, ``<microscope_object>.plugin.my_plugin.timelapse()``, and ``<microscope_object>.plugin.my_plugin.hello_world()``.

Web API routes would automatically be set up at ``/api/v1/plugin/my_plugin/identify`` (GET), ``/api/v1/plugin/my_plugin/timelapse`` (POST), and ``/api/v1/plugin/my_plugin/hello`` (GET, POST).