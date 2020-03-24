from labthings.server.find import find_component
from labthings.server.extensions import BaseExtension
from labthings.server.view import View
from labthings.server.decorators import ThingAction, ThingProperty, marshal_task

from openflexure_microscope.devel import JsonResponse, request, jsonify, taskify, abort
from openflexure_microscope.utilities import set_properties

import time
import numpy as np
import threading
import logging
from scipy import ndimage
from contextlib import contextmanager

### Autofocus utilities


class JPEGSharpnessMonitor:
    def __init__(self, microscope, timeout=60):
        self.microscope = microscope
        self.camera = microscope.camera
        self.stage = microscope.stage
        self.jpeg_sizes = []
        self.jpeg_times = []
        self.stage_positions = []
        self.stage_times = []
        self.stop_event = threading.Event()
        self.timeout = timeout
        self.keep_alive()
        self.background_thread = None

    def is_alive(self):
        if self.background_thread is None:
            return False
        else:
            return self.background_thread.is_alive()

    def should_stop(self):
        import time

        return time.time() - self.kept_alive > self.timeout

    def keep_alive(self):
        import time

        self.kept_alive = time.time()

    def start(self):
        "Start monitoring sharpness by looking at JPEG size"
        self.background_thread = threading.Thread(target=self._measure_jpegs)
        self.background_thread.start()
        return self

    def stop(self):
        "Stop the background thread"
        self.stop_event.set()
        self.background_thread.join()

    def _measure_jpegs(self):
        "Function that runs in a background thread to record sharpness"
        logging.info("Starting sharpness measurement in background thread")
        self.keep_alive()
        while not self.stop_event.is_set() and not self.should_stop():
            self.jpeg_sizes.append(self.jpeg_size())
            self.jpeg_times.append(time.time())
        if self.stop_event.is_set():
            logging.info("Cleanly stopped sharpness measurement in background thread")
        if self.should_stop():
            logging.info("Sharpness measurement timed out and has stopped")

    def jpeg_size(self):
        """Return the size of a frame from the MJPEG stream"""
        return len(self.camera.get_frame())

    def focus_rel(self, dz, backlash=False, **kwargs):
        self.keep_alive()
        self.stage_times.append(time.time())
        self.stage_positions.append(self.stage.position)
        self.stage.move_rel([0, 0, dz], backlash=backlash, **kwargs)
        self.stage_times.append(time.time())
        self.stage_positions.append(self.stage.position)
        i = len(self.stage_positions) - 2
        return i, self.stage_positions[-1][2]

    def move_data(self, istart, istop=None):
        "Extract sharpness as a function of (interpolated) z"
        global np, logging
        if istop is None:
            istop = istart + 2
        jpeg_times = np.array(self.jpeg_times)
        jpeg_sizes = np.array(self.jpeg_sizes)
        stage_times = np.array(self.stage_times)[istart:istop]
        stage_zs = np.array(self.stage_positions)[istart:istop, 2]
        start = np.argmax(jpeg_times > stage_times[0])
        stop = np.argmax(jpeg_times > stage_times[1])
        if stop < 1:
            stop = len(jpeg_times)
            logging.debug("changing stop to {}".format(stop))
        jpeg_times = jpeg_times[start:stop]
        jpeg_zs = np.interp(jpeg_times, stage_times, stage_zs)
        return jpeg_times, jpeg_zs, jpeg_sizes[start:stop]

    def sharpest_z_on_move(self, index):
        """Return the z position of the sharpest image on a given move"""
        jt, jz, js = self.move_data(index)
        return jz[np.argmax(js)]

    def data_dict(self):
        """Return the gathered data as a single convenient dictionary"""
        data = {}
        for k in ["jpeg_times", "jpeg_sizes", "stage_times", "stage_positions"]:
            data[k] = getattr(self, k)
        return data


def decimate_to(shape, image):
    """Decimate an image to reduce its size if it's too big."""
    decimation = np.max(
        np.ceil(np.array(image.shape, dtype=np.float)[: len(shape)] / np.array(shape))
    )
    return image[:: int(decimation), :: int(decimation), ...]


def sharpness_sum_lap2(rgb_image):
    """Return an image sharpness metric: sum(laplacian(image)**")"""
    # image_bw=np.mean(decimate_to((1000,1000), rgb_image),2)
    image_bw = np.mean(rgb_image, 2)
    image_lap = ndimage.filters.laplace(image_bw)
    return np.mean(image_lap.astype(np.float) ** 4)


def sharpness_edge(image):
    """Return a sharpness metric optimised for vertical lines"""
    gray = np.mean(image.astype(float), 2)
    n = 20
    edge = np.array([[-1] * n + [1] * n])
    return np.sum(
        [np.sum(ndimage.filters.convolve(gray, W) ** 2) for W in [edge, edge.T]]
    )


### Autofocus extension


def measure_sharpness(microscope, metric_fn=sharpness_sum_lap2):
    """Measure the sharpness of the camera's current view."""
    if hasattr(microscope.camera, "array"):
        return metric_fn(microscope.camera.array(use_video_port=True))


def autofocus(microscope, dz, settle=0.5, metric_fn=sharpness_sum_lap2):
    """Perform a simple autofocus routine.
    The stage is moved to z positions (relative to current position) in dz,
    and at each position an image is captured and the sharpness function 
    evaulated.  We then move back to the position where the sharpness was
    highest.  No interpolation is performed.
    dz is assumed to be in ascending order (starting at -ve values)
    """
    camera = microscope.camera
    stage = microscope.stage

    with set_properties(stage, backlash=256), stage.lock, camera.lock:
        sharpnesses = []
        positions = []
        camera.annotate_text = ""

        for _ in stage.scan_z(dz, return_to_start=False):
            positions.append(stage.position[2])
            time.sleep(settle)
            sharpnesses.append(measure_sharpness(microscope, metric_fn))

        newposition = positions[np.argmax(sharpnesses)]
        stage.move_rel([0, 0, newposition - stage.position[2]])

    return positions, sharpnesses


@contextmanager
def monitor_sharpness(microscope):
    m = JPEGSharpnessMonitor(microscope)
    m.start()
    try:
        yield m
    finally:
        m.stop()


def move_and_find_focus(microscope, dz):
    """Make a relative Z move and return the peak sharpness position"""
    with monitor_sharpness(microscope) as m:
        m.focus_rel(dz)
        return m.sharpest_z_on_move(0)


def fast_autofocus(microscope, dz=2000, backlash=None):
    """Perform a down-up-down-up autofocus"""
    with monitor_sharpness(microscope) as m, microscope.camera.lock:
        i, z = m.focus_rel(-dz / 2)
        i, z = m.focus_rel(dz)
        fz = m.sharpest_z_on_move(i)
        if backlash is None:
            i, z = m.focus_rel(-dz)  # move all the way to the start so it's consistent
        else:
            i, z = m.focus_rel(fz - z - backlash)
        m.focus_rel(fz - z)
        return m.data_dict()


def fast_up_down_up_autofocus(
    microscope, dz=2000, target_z=0, initial_move_up=True, mini_backlash=25
):
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

        mini_backlash: (optional, default 25) is a small extra move made in step
            3 to help counteract backlash.  It should be small enough that you
            would always expect there to be greater backlash than this.  Too small
            might slightly hurt accuracy, but is unlikely to be a big issue.  Too big
            may cause you to overshoot, which is a problem.
    """
    with monitor_sharpness(microscope) as m, microscope.camera.lock:
        # Ensure the MJPEG stream has started
        microscope.camera.start_stream_recording()

        df = dz  # TODO: refactor so I actually use dz in the code below!
        if initial_move_up:
            m.focus_rel(df / 2)
        # move down
        i, z = m.focus_rel(-df)
        # now inspect where the sharpest point is, and estimate the sharpness
        # (JPEG size) that we should find at the start of the Z stack
        jt, jz, js = m.move_data(i)
        best_z = jz[np.argmax(js)]
        target_s = np.interp(
            [best_z + target_z], jz[::-1], js[::-1]
        )  # NB jz is decreasing

        # now move to the start of the z stack
        i, z = m.focus_rel(
            best_z + target_z - z + mini_backlash
        )  # takes us to the start of the stack

        # We've deliberately undershot - figure out how much further we should move based on the curve
        current_js = m.jpeg_size()
        imax = np.argmax(js)  # we want to crop out just the bit below the peak
        js = js[imax:]  # NB z is in DECREASING order
        jz = jz[imax:]
        inow = np.argmax(
            js < current_js
        )  # use the curve we recorded to estimate our position
        # TODO: fancy interpolation stuff

        # So, the Z position corresponding to our current sharpness value is zs[inow]
        # That means we should move forwards, by best_z - zs[inow]
        correction_move = best_z + target_z - jz[inow]
        logging.debug(
            "Fast autofocus scan: correcting backlash by moving {} steps".format(
                correction_move
            )
        )
        m.focus_rel(correction_move)
        return m.data_dict()


class MeasureSharpnessAPI(View):
    def post(self):
        microscope = find_component("org.openflexure.microscope")

        if not microscope:
            abort(503, "No microscope connected. Unable to measure sharpness.")

        return jsonify({"sharpness": measure_sharpness(microscope)})


@ThingAction
class AutofocusAPI(View):
    """
    Run a standard autofocus
    """

    @marshal_task
    def post(self):
        payload = JsonResponse(request)
        microscope = find_component("org.openflexure.microscope")

        if not microscope:
            abort(503, "No microscope connected. Unable to autofocus.")

        # Figure out the range of z values to use
        dz = payload.param("dz", default=np.linspace(-300, 300, 7), convert=np.array)

        if microscope.has_real_stage():
            logging.info("Running autofocus...")
            task = taskify(autofocus)(microscope, dz)

            # return a handle on the autofocus task
            return task

        else:
            abort(503, "No stage connected. Unable to autofocus.")


@ThingAction
class FastAutofocusAPI(View):
    """
    Run a fast autofocus
    """

    @marshal_task
    def post(self):
        payload = JsonResponse(request)
        microscope = find_component("org.openflexure.microscope")

        if not microscope:
            abort(503, "No microscope connected. Unable to autofocus.")

        # Figure out the parameters to use
        dz = payload.param("dz", default=2000, convert=int)
        backlash = payload.param("backlash", default=25, convert=int)
        if backlash < 0:
            backlash = 0

        if microscope.has_real_stage():
            logging.info("Running autofocus...")
            task = taskify(fast_up_down_up_autofocus)(microscope, dz=dz, mini_backlash=backlash)

            # return a handle on the autofocus task
            return task

        else:
            abort(503, "No stage connected. Unable to autofocus.")


autofocus_extension_v2 = BaseExtension(
    "org.openflexure.autofocus", version="2.0.0"
)

autofocus_extension_v2.add_method(fast_autofocus, "fast_autofocus")
autofocus_extension_v2.add_method(fast_up_down_up_autofocus, "fast_up_down_up_autofocus")
autofocus_extension_v2.add_method(autofocus, "autofocus")

autofocus_extension_v2.add_view(MeasureSharpnessAPI, "/measure_sharpness")
autofocus_extension_v2.add_view(AutofocusAPI, "/autofocus")
autofocus_extension_v2.add_view(FastAutofocusAPI, "/fast_autofocus")
