import numpy as np
import logging
import cv2
import json
from PIL import Image
import os
from typing import Annotated, Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple
from fastapi.responses import FileResponse
from fastapi import HTTPException

import micat

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.invocation import CancelHook, InvocationLogger, InvocationCancelledError
from labthings_fastapi.decorators import thing_action, thing_property, fastapi_endpoint
from labthings_sangaboard import SangaboardThing
from labthings_picamera2.thing import StreamingPiCamera2
from labthings_fastapi.types.numpy import NDArray, denumpify, DenumpifyingDict
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper

StageDep = direct_thing_client_dependency(SangaboardThing, "/stage/")
CamDep = direct_thing_client_dependency(StreamingPiCamera2, "/camera/")
CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")

class MicatThing(Thing):
    @thing_action
    def run_micat(
        self,
        cam: CamDep,
        cancel: CancelHook,
        logger: InvocationLogger,
        group,
        element
    ):
        if isinstance(group, str):
            group = int(group)
        if isinstance(element, str):
            element = int(element)
        img = np.array(Image.open(cam.grab_jpeg().open()))
        micat.usafcal.export_preview(img, 'logs/preview_micat.png', group, element)

        results = micat.usafcal.analyse_image(img,g=group,e=element,smallest=True,verbose=False)

        keys = ['field_of_view', 'field_of_view_uncert', 'um_per_px', 'um_per_px_uncert', 'fov_pixels']
        logged_results = {x:results[x] for x in keys}

        micat.usafcal.export_results(results,os.path.join("logs", "micat"))
        cv2.imwrite(os.path.join("logs", "micat_img.jpeg") ,results['image'])
        logger.info(DenumpifyingDict(logged_results).model_dump())

        # TODO save image, save image with boxes, display in webapp, save results as property to read
        self.last_micat = DenumpifyingDict(logged_results).model_dump()

        return DenumpifyingDict(logged_results).model_dump()
    
    @thing_action
    def generate_preview(
            self,
            cam: CamDep,
            group,
            element,
            logger: InvocationLogger
    ):
        if isinstance(group, str):
            group = int(group)
        if isinstance(element, str):
            element = int(element)
        img = np.array(Image.open(cam.grab_jpeg().open()))
        micat.usafcal.export_preview(img, 'logs/preview_micat.png', group, element)

    @fastapi_endpoint(
            "get",
            "get_latest_preview.png",
            responses = {
                200: {
                    "description": "A preview-quality stitched image",
                    "content": {"image/png": {}}
                },
                404: {"description": "File not found"}
            },
        )
    def get_latest_preview(
            self,
            logger: InvocationLogger
        ) -> FileResponse:
        """Retrieve the latest preview image.
        """
        path = 'logs/preview_micat.png'
        logger.info(path)
        if not os.path.isfile(path):
            raise HTTPException(404, "File not found")
        return FileResponse(path)

    @thing_property
    def last_micat(self) -> dict:
        return self.thing_settings.get("last_micat", "")
    
    @last_micat.setter
    def last_micat(self, value: dict) -> None:
        self.thing_settings["last_micat"] = value