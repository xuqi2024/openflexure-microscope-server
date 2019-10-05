from openflexure_microscope.devel import (
    MicroscopeViewPlugin,
    JsonResponse,
    request,
    jsonify,
    abort,
)

import logging


class TileScanAPI(MicroscopeViewPlugin):
    def post(self):
        payload = JsonResponse(request)

        # Get params
        filename = payload.param("filename")
        temporary = payload.param("temporary", default=False, convert=bool)

        step_size = payload.param("step_size", default=[2000, 1500, 100], convert=list)
        step_size = [int(i) for i in step_size]

        grid = payload.param("grid", default=[3, 3, 5], convert=list)
        grid = [int(i) for i in grid]

        style = payload.param("style", default="raster", convert=str)
        autofocus_dz = payload.param("autofocus_dz", default=50, convert=int)
        fast_autofocus = payload.param("fast_autofocus", default=False, convert=bool)

        use_video_port = payload.param("use_video_port", default=True, convert=bool)
        resize = payload.param("size", default=None)
        if resize:
            if ("width" in resize) and ("height" in resize):
                resize = (
                    int(resize["width"]),
                    int(resize["height"]),
                )  # Convert dict to tuple
            else:
                abort(404)

        bayer = payload.param("bayer", default=False, convert=bool)
        metadata = payload.param("metadata", default={}, convert=dict)
        tags = payload.param("tags", default=[], convert=list)

        logging.info("Running tile scan...")
        task = self.microscope.task.start(
            self.plugin.tile,
            basename=filename,
            temporary=temporary,
            step_size=step_size,
            grid=grid,
            style=style,
            autofocus_dz=autofocus_dz,
            use_video_port=use_video_port,
            resize=resize,
            bayer=bayer,
            fast_autofocus=fast_autofocus,
            metadata=metadata,
            tags=tags,
        )

        # return a handle on the autofocus task
        return jsonify(task.state), 202
