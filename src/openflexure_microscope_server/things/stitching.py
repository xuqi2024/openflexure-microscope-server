from typing import Optional
import os
from subprocess import CompletedProcess, run, PIPE

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.raw_thing import raw_thing_dependency
from labthings_fastapi.dependencies.invocation import InvocationLogger
from labthings_fastapi.decorators import thing_action
from labthings_fastapi.outputs.blob import BlobOutput

from .smart_scan import SmartScanThing

SmartScanDep = raw_thing_dependency(SmartScanThing)


class JPEGBlob(BlobOutput):
    media_type = "image/jpeg"


class Stitcher(Thing):
    def __init__(self, path_to_openflexure_stitch: str):
        self._script = path_to_openflexure_stitch

    def run_subprocess(
        self,
        logger: InvocationLogger,
        cmd: list[str],
    ) -> CompletedProcess:
        """Run a  subprocess and log any output"""
        logger.info(f"Running command in subprocess: `{' '.join(cmd)}")
        output = run(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        for pipe in [output.stdout, output.stderr]:
            if pipe:
                logger.info(pipe)
        output.check_returncode()
        return output

    def images_folder(
        self, smart_scan: SmartScanDep, scan_name: Optional[str] = None
    ) -> str:
        scan_folder = smart_scan.scan_folder_path(scan_name=scan_name)
        return os.path.join(scan_folder, "images")

    @staticmethod
    def output_up_to_date(
        folder: str,
        output_filename: str,
        image_prefix: str = "image",
        image_suffix: str = ".jpg",
    ) -> bool:
        """Check if any of the images in a folder are newer than a file

        If there are no images (files with the prefix and suffix) newer than the
        `output_filename`, we return `True`, i.e. the output is up to date. If
        any image in the folder is newer, we return `False`.

        This is not flawless logic - if an update process is slow, images might be
        saved between starting that process and saving the output. Consequently,
        a `True` from this function does not guarantee the output is up to date.

        If the output file is missing, we also return `False`.
        """
        output_path = os.path.join(folder, output_filename)
        if not os.path.exists(output_path):
            return False
        mtime = os.path.getmtime(output_path)
        for fname in os.listdir(folder):
            if fname.startswith(image_prefix) and fname.endswith(image_suffix):
                if os.path.getmtime(os.path.join(folder, fname)) > mtime:
                    return False
        return True

    @thing_action
    def stitch_scan_from_stage(
        self,
        logger: InvocationLogger,
        smart_scan: SmartScanDep,
        scan_name: Optional[str] = None,
        downsample: float = 1.0,
    ) -> JPEGBlob:
        """Generate a stitched image based on stage position metadata"""
        output_fname = "stitched_from_stage.jpg"
        images_folder = self.images_folder(smart_scan=smart_scan, scan_name=scan_name)
        if self.output_up_to_date(images_folder, output_fname):
            logger.info(f"No images are newer than {output_fname}, skipping.")
        else:
            self.run_subprocess(
                logger,
                [self._script, "--stitching_mode", "only_stage_stitch", images_folder],
            )
        return JPEGBlob.from_file(os.path.join(images_folder, output_fname))

    @thing_action
    def update_scan_correlations(
        self,
        logger: InvocationLogger,
        smart_scan: SmartScanDep,
        scan_name: Optional[str] = None,
    ) -> None:
        """Generate a stitched image based on stage position metadata"""
        images_folder = self.images_folder(smart_scan=smart_scan, scan_name=scan_name)
        self.run_subprocess(
            logger, [self._script, "--stitching_mode", "only_correlate", images_folder]
        )

    @thing_action
    def stitch_scan(
        self,
        logger: InvocationLogger,
        smart_scan: SmartScanDep,
        scan_name: Optional[str] = None,
        downsample: float = 1.0,
    ) -> None:
        """Generate a stitched image based on stage position metadata"""
        images_folder = self.images_folder(smart_scan=smart_scan, scan_name=scan_name)
        self.run_subprocess(
            logger, [self._script, "--stitching_mode", "all", images_folder]
        )
