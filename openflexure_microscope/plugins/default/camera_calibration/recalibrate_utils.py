import numpy as np
import time

from picamera import PiCamera
from picamera.array import PiRGBArray, PiBayerArray


def rgb_image(camera, resize=None, **kwargs):
    """Capture an image and return an RGB numpy array"""
    with PiRGBArray(camera, size=resize) as output:
        camera.capture(output, format="rgb", resize=resize, **kwargs)
        return output.array


def flat_lens_shading_table(camera):
    """Return a flat (i.e. unity gain) lens shading table.
    
    This is mostly useful because it makes it easy to get the size
    of the array correct.  NB if you are not using the forked picamera
    library (with lens shading table support) it will raise an error.
    """
    if not hasattr(PiCamera, "lens_shading_table"):
        raise ImportError(
            "This program requires the forked picamera library with lens shading support"
        )
    return np.zeros(camera._lens_shading_table_shape(), dtype=np.uint8) + 32


def adjust_exposure_to_setpoint(camera, setpoint):
    """Adjust the camera's exposure time until the maximum pixel value is <setpoint>."""
    print("Adjusting shutter speed to hit setpoint {}".format(setpoint), end="")
    for i in range(3):
        print(".", end="")
        camera.shutter_speed = int(
            camera.shutter_speed * setpoint / np.max(rgb_image(camera))
        )
        time.sleep(1)
    print("done")


def auto_expose_and_freeze_settings(camera):
    """Freeze the settings after auto-exposing to white illumination"""
    print("Allowing the camera to auto-expose")
    camera.awb_mode = "auto"
    camera.exposure_mode = "auto"
    camera.iso = (
        0
    )  # This is important, if it's on a fixed ISO, gain might not set properly.
    for i in range(6):
        print(".", end="")
        time.sleep(0.5)
    print("done")

    print("Freezing the camera settings...")
    camera.shutter_speed = camera.exposure_speed
    print("Shutter speed = {}".format(camera.shutter_speed))
    camera.exposure_mode = "off"
    print("Auto exposure disabled")
    g = camera.awb_gains
    camera.awb_mode = "off"
    camera.awb_gains = g
    print("Auto white balance disabled, gains are {}".format(g))
    print(
        "Analogue gain: {}, Digital gain: {}".format(
            camera.analog_gain, camera.digital_gain
        )
    )
    adjust_exposure_to_setpoint(camera, 215)


def channels_from_bayer_array(bayer_array):
    """Given the 'array' from a PiBayerArray, return the 4 channels."""
    bayer_pattern = [(i // 2, i % 2) for i in range(4)]
    channels = np.zeros(
        (4, bayer_array.shape[0] // 2, bayer_array.shape[1] // 2),
        dtype=bayer_array.dtype,
    )
    for i, offset in enumerate(bayer_pattern):
        # We simplify life by dealing with only one channel at a time.
        channels[i, :, :] = np.sum(
            bayer_array[offset[0] :: 2, offset[1] :: 2, :], axis=2
        )

    return channels


def lst_from_channels(channels):
    """Given the 4 Bayer colour channels from a white image, generate a LST."""
    full_resolution = np.array(channels.shape[1:]) * 2  # channels have been binned
    # lst_resolution = list(np.ceil(full_resolution / 64.0).astype(int))
    lst_resolution = [(r // 64) + 1 for r in full_resolution]
    # NB the size of the LST is 1/64th of the image, but rounded UP.
    print("Generating a lens shading table at {}x{}".format(*lst_resolution))
    lens_shading = np.zeros([channels.shape[0]] + lst_resolution, dtype=np.float)
    for i in range(lens_shading.shape[0]):
        image_channel = channels[i, :, :]
        iw, ih = image_channel.shape
        ls_channel = lens_shading[i, :, :]
        lw, lh = ls_channel.shape
        # The lens shading table is rounded **up** in size to 1/64th of the size of
        # the image.  Rather than handle edge images separately, I'm just going to
        # pad the image by copying edge pixels, so that it is exactly 32 times the
        # size of the lens shading table (NB 32 not 64 because each channel is only
        # half the size of the full image - remember the Bayer pattern...  This
        # should give results very close to 6by9's solution, albeit considerably
        # less computationally efficient!
        padded_image_channel = np.pad(
            image_channel, [(0, lw * 32 - iw), (0, lh * 32 - ih)], mode="edge"
        )  # Pad image to the right and bottom
        print(
            "Channel shape: {}x{}, shading table shape: {}x{}, after padding {}".format(
                iw, ih, lw * 32, lh * 32, padded_image_channel.shape
            )
        )
        # Next, fill the shading table (except edge pixels).  Please excuse the
        # for loop - I know it's not fast but this code needn't be!
        box = 3  # We average together a square of this side length for each pixel.
        # NB this isn't quite what 6by9's program does - it averages 3 pixels
        # horizontally, but not vertically.
        for dx in np.arange(box) - box // 2:
            for dy in np.arange(box) - box // 2:
                ls_channel[:, :] += (
                    padded_image_channel[16 + dx :: 32, 16 + dy :: 32] - 64
                )
        ls_channel /= box ** 2
        # The original C code written by 6by9 normalises to the central 64 pixels in each channel.
        # ls_channel /= np.mean(image_channel[iw//2-4:iw//2+4, ih//2-4:ih//2+4])
        # I have had better results just normalising to the maximum:
        ls_channel /= np.max(ls_channel)
        # NB the central pixel should now be *approximately* 1.0 (may not be exactly
        # due to different averaging widths between the normalisation & shading table)
        # For most sensible lenses I'd expect that 1.0 is the maximum value.
        # NB ls_channel should be a "view" of the whole lens shading array, so we don't
        # need to update the big array here.

    # What we actually want to calculate is the gains needed to compensate for the
    # lens shading - that's 1/lens_shading_table_float as we currently have it.
    gains = 32.0 / lens_shading  # 32 is unity gain
    gains[gains > 255] = 255  # clip at 255, maximum gain is 255/32
    gains[gains < 32] = 32  # clip at 32, minimum gain is 1 (is this necessary?)
    lens_shading_table = gains.astype(np.uint8)
    return lens_shading_table[::-1, :, :].copy()


def recalibrate_camera(camera):
    """Reset the lens shading table and exposure settings.

    This method first resets to a flat lens shading table, then auto-exposes,
    then generates a new lens shading table to make the current view uniform.
    It should be run when the camera is looking at a uniform white scene.

    NB the only parameter ``camera`` is a ``PiCamera`` instance and **not** a
    ``StreamingCamera``.
    """
    camera.lens_shading_table = flat_lens_shading_table(camera)
    _ = rgb_image(camera)  # for some reason the camera won't work unless I do this!

    with PiBayerArray(camera) as a:
        camera.capture(a, format="jpeg", bayer=True)
        raw_image = a.array.copy()

    # Now we need to calculate a lens shading table that would make this flat.
    # raw_image is a 3D array, with full resolution and 3 colour channels.  No
    # de-mosaicing has been done, so 2/3 of the values are zero (3/4 for R and B
    # channels, 1/2 for green because there's twice as many green pixels).
    channels = channels_from_bayer_array(raw_image)
    lens_shading_table = lst_from_channels(channels)

    camera.lens_shading_table = lens_shading_table
    _ = rgb_image(camera)

    # Fix the AWB gains so the image is neutral
    channel_means = np.mean(np.mean(rgb_image(camera), axis=0, dtype=np.float), axis=0)
    old_gains = camera.awb_gains
    camera.awb_gains = (
        channel_means[1] / channel_means[0] * old_gains[0],
        channel_means[1] / channel_means[2] * old_gains[1],
    )
    time.sleep(1)
    # Ensure the background is bright but not saturated
    adjust_exposure_to_setpoint(camera, 230)


if __name__ == "__main__":
    with PiCamera() as camera:
        camera.start_preview()
        time.sleep(3)
        print("Recalibrating...")
        recalibrate_camera(camera)
        print("Done.")
        time.sleep(2)
