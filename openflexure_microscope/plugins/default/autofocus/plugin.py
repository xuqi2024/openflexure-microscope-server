import time
import logging
import numpy as np
from contextlib import contextmanager

from openflexure_microscope.utilities import set_properties

from .focus_utils import sharpness_sum_lap2, JPEGSharpnessMonitor
from .api import MeasureSharpnessAPI, AutofocusAPI, FastAutofocusAPI

from openflexure_microscope.devel import MicroscopePlugin

class AutofocusPlugin(MicroscopePlugin):
    """
    Basic autofocus plugin
    """

    api_views = {
        '/measure_sharpness': MeasureSharpnessAPI,
        '/autofocus': AutofocusAPI,
        '/fast_autofocus': FastAutofocusAPI,
    }

    ### SLOW AUTOFOCUS

    def autofocus(self, dz, settle=0.5, metric_fn=sharpness_sum_lap2):
        """Perform a simple autofocus routine.
        The stage is moved to z positions (relative to current position) in dz,
        and at each position an image is captured and the sharpness function 
        evaulated.  We then move back to the position where the sharpness was
        highest.  No interpolation is performed.
        dz is assumed to be in ascending order (starting at -ve values)
        """
        camera = self.microscope.camera
        stage = self.microscope.stage

        with set_properties(stage, backlash=256), stage.lock, camera.lock:
            sharpnesses = []
            positions = []
            camera.annotate_text = ""

            for _ in stage.scan_z(dz, return_to_start=False):
                positions.append(stage.position[2])
                time.sleep(settle)
                sharpnesses.append(self.measure_sharpness(metric_fn))

            newposition = positions[np.argmax(sharpnesses)]
            stage.move_rel([0, 0, newposition - stage.position[2]])

        return positions, sharpnesses

    def measure_sharpness(self, metric_fn=sharpness_sum_lap2):
        """Measure the sharpness of the camera's current view."""
        return metric_fn(self.microscope.camera.array(use_video_port=True))

    ### FAST AUTOFOCUS

    @contextmanager
    def monitor_sharpness(self):
        m = JPEGSharpnessMonitor(self.microscope)
        m.start()
        try:
            yield m
        finally:
            m.stop()

    def move_and_find_focus(self, dz):
        """Make a relative Z move and return the peak sharpness position"""
        with self.monitor_sharpness() as m:
            m.focus_rel(dz)
            return m.sharpest_z_on_move(0)


    def fast_autofocus(self, dz=2000, backlash=None):
        """Perform a down-up-down-up autofocus"""
        with self.monitor_sharpness() as m:
            i, z = m.focus_rel(-dz/2)
            i, z = m.focus_rel(dz)
            fz = m.sharpest_z_on_move(i)
            if backlash is None:
                i, z = m.focus_rel(-dz) # move all the way to the start so it's consistent
            else:
                i, z = m.focus_rel(fz - z - backlash)
            m.focus_rel(fz - z)
            return m.data_dict()

    def fast_up_down_up_autofocus(self, dz=2000, target_z=0, initial_move_up=True, mini_backlash=150):
        """Autofocus by measuring on the way down, and moving back up with feedback.

        This autofocus method is very efficient, as it only passes the peak once.
        The sequence of moves it performs is:

        1.  Move to the top of the range `dz/2` (can be disabled)

        2.  Move down by `dz` while monitoring JPEG size to find the focus.

        3.  Move back up to the `target_z` position, relative to the sharpest image.

        4.  Measure the sharpness, and compare against the curve recorded in (2) to \\
            estimate how much further we need to go.  Make this move, to reach our \\
            target position.

        Moving back to the target position in two steps allows us to correct for
        backlash, by using the sharpness-vs-z curve as a rough encoder for Z.

        Parameters:
            dz: number of steps over which to scan (optional, default 2000)

            target_z: we aim to finish at this position, relative to focus.  This may 
                be useful if, for example, you want to acquire a stack of images in Z. 
                It is optional, and the default value of 0 will finish at the focus.

            initial_move_up: (optional, default True) set this to `False` to move down
                from the starting position.  Mostly useful if you're able to combine
                the initial move with something else, e.g. moving to the next scan point.

            mini_backlash: (optional, default 50) is a small extra move made in step
                3 to help counteract backlash.  It should be small enough that you
                would always expect there to be greater backlash than this.  Too small
                might slightly hurt accuracy, but is unlikely to be a big issue.  Too big
                may cause you to overshoot, which is a problem.
        """
        with self.monitor_sharpness() as m, self.microscope.camera.lock:
            # Ensure the MJPEG stream has started
            self.microscope.camera.start_stream_recording()

            df = dz #TODO: refactor so I actually use dz in the code below!
            if initial_move_up:
                m.focus_rel(df/2)
            # move down
            i, z = m.focus_rel(-df)
            # now inspect where the sharpest point is, and estimate the sharpness
            # (JPEG size) that we should find at the start of the Z stack
            jt, jz, js = m.move_data(i)
            best_z = jz[np.argmax(js)]
            target_s = np.interp([best_z+target_z], jz[::-1], js[::-1]) #NB jz is decreasing

            # now move to the start of the z stack
            i, z = m.focus_rel(best_z + target_z - z + mini_backlash) # takes us to the start of the stack

            # We've deliberately undershot - figure out how much further we should move based on the curve
            current_js = m.jpeg_size()
            imax = np.argmax(js) # we want to crop out just the bit below the peak
            js = js[imax:] # NB z is in DECREASING order
            jz = jz[imax:]
            inow = np.argmax(js < current_js) # use the curve we recorded to estimate our position
            # TODO: fancy interpolation stuff

            # So, the Z position corresponding to our current sharpness value is zs[inow]
            # That means we should move forwards, by best_z - zs[inow]
            correction_move = best_z + target_z - jz[inow]
            logging.debug("Fast autofocus scan: correcting backlash by moving {} steps".format(correction_move))
            m.focus_rel(correction_move)
            return m.data_dict()

