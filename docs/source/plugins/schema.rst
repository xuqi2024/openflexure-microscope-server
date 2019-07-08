Adding a GUI
=====================

Introduction
------------

In order to bind user-interface elements to your plugin, an ``api_schema`` variable must be included in your microscope plugin, similar to your ``api_views``.

This variable must be in the form of a dictionary, with all data able to be parsed into JSON. Because of this requirement, it is suggested that you create your API schema as a JSON file, and load that file as a dictionary into your plugin. For example:

.. code-block:: python

    import json

    HERE = os.path.dirname(os.path.realpath(__file__))  # Find the full path of your plugin Python file
    SCHEMA_PATH = os.path.join(HERE, "schema.json")  # Find the full path of the adjascent JSON file

    class MyPluginClass(MicroscopePlugin):

        with open(SCHEMA_PATH, 'r') as sc:  # Open the JSON file
            api_schema = json.load(sc)  # Load the JSON file into the api_schema dictionary

Throughout this documentation, all example of ``api_schema`` sections will be in JSON format. Keep in mind however that it is possible to directly define your ``api_schema`` as a dictionary, without loading an external file.


Forms from ``api_schema``
-------------------------

The ``api_schema`` object essentially describes HTML forms, which it is up to the client to render. The form is constructed by specifying a set of components, and their values. A form can update it's values by sending a GET request to the API route bound to that form, and can send it's current values via a POST request to *this same API route*.

Each component in the form has a ``name`` property, which must match up to a property your API route expects in JSON POST requests, and returns in JSON GET requests.

Structure of ``api_schema``
---------------------------

Root level
++++++++++

The root of your ``api_schema`` expects 3 properties:

``id`` - A unique ID to give your client-side plugin

``icon`` - The name of a Material Design icon to use for your plugin

``forms`` - An array of forms as described below

Form level
++++++++++

Your plugin can contain multiple forms. For example, if your plugin creates several API routes, you will need a separate form for each route.

Each form is described by a JSON object, with the following properties:

``name`` - A human-readable name for the form 

``route`` - String of the corresponding API route. *Must* match a route defined in your ``api_views`` dictionary

``selfUpdate`` *(optional)* - Whether the client should automatically update form component values with a GET request to your API route

``isTask`` *(optional)* - Whether the client should treat your API route as a long-running task

``submitLabel`` *(optional)* - String to place inside of the form's submit button

``schema`` - An array of form components as described below

Component level
+++++++++++++++

Each form can (and probably should) contain multiple components. For example, if your API route expects several properties in POST requests, each property can be bound to a form component.

Upon form submission, the form data will be converted into a JSON object of key-value pairs, where the key is the components ``name``, and the value is it's current value.

On load, the form will make a GET request to it's API route, an expects a JSON object of key-value pairs in the same format (keys will be matched to component names).

An overview of available components, and their properties, can be found below.

Arranging components
^^^^^^^^^^^^^^^^^^^^

You can request that the client render several components in a horizontal grid by placing them in an array. You cannot nest arrays however. Each component in the array will be rendered with equal width as far as possible.

Overview of components
----------------------

.. list-table::
    :widths: 10 10 40 20
    :header-rows: 1
    :stub-columns: 1

    * - fieldType
      - Data type
      - Properties
      - Example
    * - checkList
      - [str, str,...]
      - **name** (str) Unique name of the component

        **label** (str) Friendly label for the component

        **value** ([str, str,...]) List of selected options
      
        **options** ([str, str,...]) List of all options
        
      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/checkList.png 
    * - htmlBlock
      - N/A
      - **name** (str) Unique name of the component

        **label** (str) Friendly label for the component

        **content** (str) HTML string to be rendered

      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/htmlBlock.png 
    * - keyvalList
      - dict
      - **name** (str) Unique name of the component

        **value** (dict) Dictionary of key-value pairs

      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/keyvalList.png 
    * - labelInput
      - str
      - **name** (str) Unique name of the component

        **label** (str) Friendly label for the component

        **value** (str) Value of the editable label text

      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/labelInput.png 
    * - numberInput
      - int
      - **name** (str) Unique name of the component

        **label** (str) Friendly label for the component

        **value** (int) Value of the input

        **placeholder** (int) Placeholder value

      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/numberInput.png 
    * - radioList
      - String
      - **name** (str) Unique name of the component

        **label** (str) Friendly label for the component

        **value** (str) Currently selected option
      
        **options** ([str, str,...]) List of all options

      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/radioList.png 
    * - selectList
      - str
      - **name** (str) Unique name of the component

        **label** (str) Friendly label for the component

        **value** (str) Currently selected option
      
        **options** ([str, str,...]) List of all options

      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/selectList.png 
    * - tagList
      - [str, str,...]
      - **name** (str) Unique name of the component

        **value** ([str, str,...]) List of tag strings

      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/tagList.png 
    * - textInput
      - str
      - **name** (str) Unique name of the component

        **label** (str) Friendly label for the component

        **value** (int) Value of the input

        **placeholder** (str) Placeholder value

      - .. figure:: https://openflexure.gitlab.io/assets/plugin-form-components/textInput.png 

JSON form example
-----------------

.. literalinclude:: schema_example.json
  :language: JSON


.. toctree::
   :maxdepth: 1

   ./schema/json_schema.rst