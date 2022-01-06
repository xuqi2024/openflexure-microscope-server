"""
Configuration functions relating to extensions - mostly enabling/disabling them.
"""
import logging
from ..config import user_configuration

def load_config_and_fix_keys():
    """Load the configuration file and ensure relevant keys exist"""
    configuration = user_configuration.load()

    # Make sure the relevant keys are present in the configuration
    for key in ("extensions_enabled", "extensions_disabled"):
        if key not in configuration:
            configuration[key] = []

    return configuration

def enable_extension(entry_point_value):
    """Enable an extension in the configuration file.
    
    WARNING: this should not be run when the server is running!"""
    configuration = load_config_and_fix_keys()
    try:
        configuration["extensions_disabled"].remove(entry_point_value)
        logging.info(f"Removed {entry_point_value} from extensions_disabled")
    except ValueError:
        pass # this just means it wasn't in the list

    if entry_point_value in configuration["extensions_enabled"]:
        logging.info(f"{entry_point_value} was already in extensions_enabled")
    else:
        configuration["extensions_enabled"].append(entry_point_value)
        logging.info(f"Added {entry_point_value} to extensions_enabled")

    user_configuration.save(configuration)
    

def disable_extension(entry_point_value):
    """Disable an extension in the configuration file.
    
    WARNING: this should not be run when the server is running!"""
    configuration = load_config_and_fix_keys()

    # Make sure the relevant keys are present in the configuration
    for key in ("extensions_enabled", "extensions_disabled"):
        if key not in configuration:
            configuration[key] = []
            
    try:
        configuration["extensions_enabled"].remove(entry_point_value)
        logging.info(f"Removed {entry_point_value} from extensions_enabled")
    except ValueError:
        pass # this just means it wasn't in the list

    if entry_point_value in configuration["extensions_disabled"]:
        logging.info(f"{entry_point_value} was already in extensions_disabled")
    else:
        configuration["extensions_disabled"].append(entry_point_value)
        logging.info(f"Added {entry_point_value} to extensions_disabled")

    user_configuration.save(configuration)


def extensions_enabled():
    configuration = load_config_and_fix_keys()
    return configuration["extensions_enabled"]


def extensions_disabled():
    configuration = load_config_and_fix_keys()
    return configuration["extensions_disabled"]

