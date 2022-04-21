"""
Convenience imports for developers.

Here we include some classes used frequently in plugin development, 
as well as some Flask imports to simplify API route development
"""

# Flask things
from flask import Response, abort, escape, request

# Task management
from labthings import current_action as current_task
from labthings import update_action_data as update_task_data
from labthings import update_action_progress as update_task_progress

__all__ = [
    "current_task",
    "update_task_progress",
    "update_task_data",
    "abort",
    "escape",
    "Response",
    "request",
]

from logging import warning
warning(
    "The openflexure_microscope.devel module is deprecated "
    "and will be removed in future versions."
)