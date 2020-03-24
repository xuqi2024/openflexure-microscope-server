from openflexure_microscope.microscope import Microscope

import logging


default_microscope = Microscope()

# Restore loaded capture array to camera object
logging.debug("Restoring captures...")
default_microscope.camera.rebuild_captures()

logging.debug("Microscope successfully attached!")
