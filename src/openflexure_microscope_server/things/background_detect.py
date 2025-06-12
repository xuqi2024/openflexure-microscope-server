from typing import Mapping, Optional
import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel
from scipy.stats import norm

from labthings_fastapi.thing import Thing
from labthings_fastapi.decorators import thing_action, thing_property
from .camera import CameraDependency as CamDep


class ChannelDistributions(BaseModel):
    means: list[float]
    standard_deviations: list[float]
    colorspace: str = "LUV"


class BackgroundDetectThing(Thing):
    @thing_property
    def background_distributions(self) -> Optional[ChannelDistributions]:
        """The statistics of the background image"""
        bd = self.thing_settings.get("background_distributions", None)
        if bd:
            return ChannelDistributions(**bd)
        return None

    @background_distributions.setter
    def background_distributions(self, value: Optional[ChannelDistributions]) -> None:
        try:
            self.thing_settings["background_distributions"] = value.model_dump()
        except AttributeError:
            self.thing_settings["background_distributions"] = None

    @thing_property
    def tolerance(self) -> float:
        """How many standard deviations to allow for the background"""
        return self.thing_settings.get("tolerance", 7)

    @tolerance.setter
    def tolerance(self, value: float) -> None:
        self.thing_settings["tolerance"] = value

    @thing_property
    def fraction(self) -> float:
        """How much of the image needs to be not background to label as sample"""
        return self.thing_settings.get("fraction", 25)

    @fraction.setter
    def fraction(self, value: float) -> None:
        self.thing_settings["fraction"] = value

    def background_mask(self, image: np.ndarray) -> np.ndarray:
        """Calculate a binary image, showing whether each pixel is background

        The image should be in LUV format, the ouput will be binary with the
        same shape in the first two dimensions.
        """
        d = self.background_distributions
        if not d:
            raise RuntimeError(
                "Background is not set: you need to calibrate background detection."
            )
        # This image is in LUV space. But the brightness (L) often changes as the
        # height of the sample changes. Hence in the line below we are only using
        # the UV (colour) channels.
        return np.all(
            np.abs(image[:, :, 1:] - np.array(d.means[1:])[np.newaxis, np.newaxis, :])
            < np.array(d.standard_deviations[1:])[np.newaxis, np.newaxis, :]
            * self.tolerance,
            axis=2,
        )

    @thing_action
    def background_fraction(self, cam: CamDep) -> float:
        """Determine what fraction of the current image is background

        This action will acquire a new image from the preview stream, then
        evaluate whether it is foreground or background, by comparing it
        too the saved statistics. This is done on a per-pixel basis, and
        the returned value (between 0 and 100) is the fraction of the image
        that is background.
        """
        current_image = cam.grab_jpeg()
        current_image = np.array(Image.open(current_image.open()))

        # we're working in the LUV colourspace as it collect colours together in a human-intuitive way
        current_image_luv = cv2.cvtColor(current_image, cv2.COLOR_RGB2LUV)
        mask = self.background_mask(current_image_luv)
        return np.count_nonzero(mask) / np.prod(mask.shape) * 100

    @thing_action
    def image_is_sample(self, cam: CamDep) -> bool:
        """Label the current image as either background or sample"""
        b_fraction = self.background_fraction(cam)
        fraction_threshold = self.fraction

        return (100 - b_fraction) > fraction_threshold

    @thing_action
    def set_background(self, cam: CamDep):
        """Grab an image, and use its statistics to set the background

        This should be run when the microscope is looking at an empty region,
        and will calculate the mean and standard deviation of the pixel values
        in the LUV colourspace. These values will then be used to compare
        future images to the distribution, to determine if each pixel is
        foreground or background.
        """
        background = cam.grab_jpeg()
        background = np.array(Image.open(background.open()))

        # we're working in the LUV colourspace as it collect colours together in a human-intuitive way
        background_luv = cv2.cvtColor(background, cv2.COLOR_RGB2LUV)

        ch1 = (background_luv.T[0]).flatten()
        ch2 = (background_luv.T[1]).flatten()
        ch3 = (background_luv.T[2]).flatten()

        points = np.array([np.asarray(ch1), np.asarray(ch2), np.asarray(ch3)]).T

        # we get the mean and standard deviation of values in each channel
        mu, std = np.apply_along_axis(norm.fit, 0, points)

        self.background_distributions = ChannelDistributions(
            means=mu.tolist(),
            standard_deviations=std.tolist(),
            colorspace="LUV",
        )

    @property
    def thing_state(self) -> Mapping:
        bd = self.background_distributions
        return {
            "background_distributions": bd.model_dump() if bd else None,
            "tolerance": self.tolerance,
            "fraction": self.fraction,
        }
