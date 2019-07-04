import importlib
import os
import inspect
import logging


class ConColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def module_from_file(plugin_path):
    # Expand environment variables in path string
    plugin_path = os.path.expandvars(plugin_path)
    # Expand user directory in path string
    plugin_path = os.path.expanduser(plugin_path)

    # Check if the path is to a file
    if not os.path.isfile(plugin_path):
        logging.warning(ConColors.FAIL + "No valid plugin found at {}.".format(plugin_path) + ConColors.ENDC)
        return None, None, None

    else:
        # Get name of plugin from the file
        plugin_name = os.path.splitext(os.path.basename(plugin_path))[0]

        plugin_spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        plugin_module = importlib.util.module_from_spec(plugin_spec)

        return plugin_spec, plugin_module, plugin_name

def check_module(module_path):
    """
    Used to check if a module exists, without ever importing it.

    This checks each nested level separately to avoid raising exceptions.
    For example, checking "mymodule.submodule.subsubmodule" will first 
    check if 'mymodule' exists, then if it does, it will check
    'mymodule.submodule', and so on.
    """
    module_split = module_path.split(".")
    spec_path = ""

    for module_level in module_split:
        spec_path += ".{}".format(module_level)
        spec_path = spec_path.strip(".")

        logging.debug("Checking {}".format(spec_path))

        # Try to find a module loader for the plugin path
        plugin_spec = importlib.util.find_spec(spec_path)

        # If plugin spec doesn't exist, return False early
        if plugin_spec is None:
            return False

    # If all checks pass, return True
    return True


def name_from_module(plugin_path):
    path_array = plugin_path.split('.')

    # Truncate namespace of default plugins
    if path_array[0:2] == ['openflexure_microscope', 'plugins']:
        path_array = path_array[2:]
    
    return '/'.join(path_array)


def load_plugin_module(plugin_path):

    # If the loader was found (i.e. plugin probably exists)
    if check_module(plugin_path):
        try:
            plugin_module = importlib.import_module(plugin_path)
            plugin_name = name_from_module(plugin_path)
        except Exception as e:
            logging.error("Error loading plugin.")
            logging.error(e)
            return None, None

    # If no loader was found, try finding a file from path
    else:
        plugin_spec, plugin_module, plugin_name = module_from_file(plugin_path)
        # If a valid plugin was found
        if plugin_spec and plugin_module:
            # Execute the module, so we have access to it
            plugin_spec.loader.exec_module(plugin_module)

    return plugin_module, plugin_name


def load_plugin_class(plugin_path, plugin_class_name):
    plugin_module, plugin_name = load_plugin_module(plugin_path)
    if plugin_module:
        # Now try to extract the class
        try:
            plugin_class = getattr(plugin_module, plugin_class_name)
        except AttributeError:
            logging.warning(ConColors.FAIL + "Class {} does not exist in plugin {}. Skipping.".format(plugin_class_name, plugin_path) + ConColors.ENDC)
            return None, None
        else:
            return plugin_class, plugin_name
    else:
        return None, None


def class_from_map(plugin_map):
    plugin_arr = plugin_map.split(':')

    if not len(plugin_arr) == 2:
        logging.warning(ConColors.WARNING + "Malformed plugin map {}. Skipping.".format(plugin_map) + ConColors.ENDC)
        return None, None
    else:
        return load_plugin_class(*plugin_arr)


class PluginMount(object):
    """
    A mount-point for all loaded plugins. Attaches to a Microscope object.

    Args:
        parent (:py:class:`openflexure_microscope.microscope.Microscope`): The parent Microscope object to attach to.
    """
    def __init__(self, parent):
        self.parent = parent
        self.plugins = []  # List of plugin objects
        self.schemas = []  # List of plugin schemas
        logging.info("Creating plugin mount")

    @property
    def state(self):
        return [m[0] for m in self.members]

    @property
    def members(self):
        ignores = ['state', 'members', 'attach']
        plugin_array = []
        for obj_name in dir(self):
            if not obj_name in ignores and not obj_name[:2] == '__':
                obj = getattr(self, obj_name)
                if isinstance(obj, MicroscopePlugin):
                    plugin_members = [member for member in inspect.getmembers(obj) if not member[0][:2] == '__']
                    plugin_info = (obj_name, plugin_members)
                    plugin_array.append(plugin_info)
        return plugin_array

    def attach(self, plugin_map):
        """
        Attach a MicroscopePlugin instance to the plugin mount.

        Args:
            plugin_map (str): A plugin map describing the file or module to load a MicroscopePlugin child from. Maps should be in the format 'module.to.load:ClassName' or '/path/to/file:ClassName'.
        """
        plugin_class, plugin_name = class_from_map(plugin_map)

        if plugin_class is not None:

            pythonsafe_plugin_name = plugin_name.replace("/", "_")

            if plugin_class and plugin_name:
                plugin_object = plugin_class()

                if hasattr(self, plugin_name):  # If a plugin with the same name is already attached.
                    logging.warning(ConColors.WARNING + "A plugin named {} has already been loaded. Skipping {}.".format(plugin_name, plugin_map) + ConColors.ENDC)

                elif isinstance(plugin_object, MicroscopePlugin):  # If plugin_object is an instance of MicroscopePlugin
                    # Attach plugin_object to the plugin mount
                    setattr(self, pythonsafe_plugin_name, plugin_object)
                    self.plugins.append((plugin_name, plugin_object))

                    # Grant plugin access to the hardware
                    plugin_object.microscope = self.parent

                    logging.info(ConColors.OKGREEN + "Plugin {} loaded as {}.".format(plugin_map, plugin_name) + ConColors.ENDC)

        else:
            logging.error("Error loading plugin. Moving on.")

class MicroscopePlugin:
    """
    Parent class for all microscope plugins.

    Initially only defines an empty object for microscope. All plugins
    must be an instance of this class to successfully attach to PluginMount.
    """

    api_views = {}  # Initially empty dictionary of API views associated with the plugin

    def __init__(self):
        self.microscope = None  #: :py:class:`openflexure_microscope.microscope.Microscope`: Microscope object
