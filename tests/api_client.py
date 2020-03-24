import requests
from PIL import Image
from io import BytesIO
import numpy as np


class APIconnection:
    def __init__(self, host="localhost", port=5000, api_ver="v1"):
        self.base = self.build_base(host=host, port=port, api_ver=api_ver)

    def build_base(self, host, port, api_ver):
        return "http://{}:{}/api/{}".format(host, port, api_ver)

    def uri(self, suffix):
        return self.base + suffix

    def get(self, route, json=True, timeout=5):
        r = requests.get(self.uri(route), timeout=timeout)
        if json:
            return r.json()
        else:
            return r

    def post(self, route, json=None, timeout=5):
        r = requests.post(self.uri(route), json=json, timeout=timeout)
        return r.json()

    def delete(self, route, timeout=5):
        r = requests.delete(self.uri(route), timeout=timeout)
        return r.json()

    def set_overlay(self, message="", size=50):
        json = {"text": message, "size": size}
        return self.post("/camera/overlay", json=json)

    def get_overlay(self):
        return self.get("/camera/overlay")

    def get_config(self):
        return self.get("/config")

    def set_config(self, config_dict):
        return self.post("/config", json=config_dict)

    def get_state(self):
        return self.get("/state")

    def start_preview(self):
        return self.post("/camera/preview/start")

    def stop_preview(self):
        return self.post("/camera/preview/stop")

    def move_by(self, x=0, y=0, z=0):
        json = {"x": x, "y": y, "z": z}
        return self.post("/stage/position", json=json)

    def new_capture(self, use_video_port=True, keep_on_disk=False, resize=None):
        json = {"keep_on_disk": keep_on_disk, "use_video_port": use_video_port}

        if resize:
            json["size"] = {"width": resize[0], "height": resize[1]}

        return self.post("/camera/capture", json=json)

    def get_capture(self, capture_id):
        uri_route = "/camera/capture/{}/download".format(capture_id)
        r = self.get(uri_route, json=False)
        img = Image.open(BytesIO(r.content))
        array = np.asarray(img, dtype=np.int32)
        return array

    def del_capture(self, capture_id):
        uri_route = "/camera/capture/{}".format(capture_id)
        return self.delete(uri_route)

    def capture(
        self,
        use_video_port=True,
        keep_on_disk=False,
        delete_after_use=True,
        resize=None,
    ):
        p = self.new_capture(
            use_video_port=use_video_port, keep_on_disk=keep_on_disk, resize=resize
        )
        capture_id = p["metadata"]["id"]
        img_array = self.get_capture(capture_id)

        if delete_after_use:
            self.del_capture(capture_id)

        return img_array

    def set_zoom(self, zoom_value=1.0):
        json = {"zoom_value": zoom_value}
        return self.post("/camera/zoom", json=json)

    def get_zoom(self):
        return self.get("/camera/zoom")
