OpenFlexure eV GUI
==================

Introduction
------------

The main client application for the OpenFlexure Microscope, OpenFlexure eV, can render simple GUIs (graphical user interfaces) for extensions.

We define our user interface by making use of the extensions general metadata, added using the ``add_meta`` function. This function adds arbitrary additional data to your extensions web API description, for example:

.. code-block:: python

    # Create your extension object
    my_extension = BaseExtension("com.myname.myextension", version="0.0.0")

    ...

    my_extension.add_meta("myKey", "My metadata value")

OpenFlexure eV will recognise the ``gui`` metadata key, and render properly structured descriptions of a GUI in the format described below. The ``gui`` data essentially describes HTML forms, which it is up to the client to render. The form is constructed by specifying a set of components, and their values. 

Each component in the form has a ``name`` property, which must match up to a property your API route expects in JSON POST requests, and returns in JSON GET requests.


Structure of ``gui``
---------------------------

Root level
++++++++++

The root of your ``gui`` dictionary expects 2 properties:

``icon`` - The name of a Material Design icon to use for your plugin

``forms`` - An array of forms as described below

Form level
++++++++++

Your extension can contain multiple forms. For example, if your extension creates several API routes, you will need a separate form for each route.

Each form is described by a JSON object, with the following properties:

``name`` - A human-readable name for the form 

``route`` - String of the corresponding API route. *Must* match a route defined in your ``api_views`` dictionary

``isTask`` *(optional)* - Whether the client should treat your API route as a long-running task

``isCollapsible`` *(optional)* - Whether the form can be collapsed into an accordion

``submitLabel`` *(optional)* - String to place inside of the form's submit button

``schema`` - List of dictionaries. Each dictionary element describes a form component.

Component level
+++++++++++++++

Each form can (and probably should) contain multiple components. For example, if your API route expects several parameters in a POST requests, each parameter can be bound to a form component.

Upon form submission, the form data will be converted into a JSON object of key-value pairs, where the key is the components ``name``, and the value is it's current value.

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

**Note:** Basic input types (``textInput``, ``numberInput``) can also include additional attributes for HTML input elements inputs (e.g. ``placeholder``, ``required``, ``min``, ``max``). These additional attributes will be forwarded to the rendered HTML elements.

Building the GUI
----------------

Once you have a dictionary describing your GUI, use the :py:meth:`openflexure_microscope.api.utilities.gui.build_gui` function to fill in and expand any information required to have it properly function. This function expands your ``route`` values to include your extensions full URI, and handles returning dynamic GUIs.

For example:

.. code-block:: python

    my_gui = {...}

    # Create your extension object
    my_extension = BaseExtension("com.myname.myextension", version="0.0.0")

    ...

    my_extension.add_meta("gui", build_gui(my_gui, my_extension))

Dynamic GUIs
------------

Instead of passing a static dictionary to :py:meth:`openflexure_microscope.api.utilities.gui.build_gui`, you can instead pass a callable function which returns a dictionary. This function is then called every time a client requests a description of active extensions.

Using a callable has the advantage of allowing your extensions GUI to be updated as it is used. This could be as simple as changing ``value`` parameters of components (to show up-to-date default form values), but could be used to entirely change the GUI form as it is used, for example dynamically changing options in select boxes.

For example, this could take the form:

.. code-block:: python

    def create_dynamic_form():
        ...
        generated_form_dict = {...}
        return generated_form_dict

    # Create your extension object
    my_extension = BaseExtension("com.myname.myextension", version="0.0.0")

    ...

    my_extension.add_meta("gui", build_gui(create_dynamic_form, my_extension))


Complete example
----------------

Adding a GUI to our previous timelapse example extension becomes:

.. literalinclude:: ./example_extension/07_ev_gui.py
