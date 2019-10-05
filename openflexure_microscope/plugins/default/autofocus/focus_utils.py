import time
import numpy as np
import threading
import logging
from scipy import ndimage


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
