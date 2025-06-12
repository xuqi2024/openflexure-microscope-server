"""This submodule deals with colour conversion.

Colour conversion can be done with OpenCV or with scikit-image,
but they are both very large dependencies for one colour conversion.

This submodule uses code derived from scikit-image but removes a lot
of extra generalisation needed for situations where the colour channel
is not the last axis.

As such this specific file is licenses 3-Clause BSD and copyright Scikit-image
"""

# To minimise code changes from scikit-image some linter checks are turned off

# Turning off commented out code checker as a lot of the maths functions
# in comments look like commented out code.
# ruff: noqa: ERA001

# Turning off PEP8 variable checking as upper case mathematical labels are used
# for colour channels.
# ruff: noqa: N803
# ruff: noqa: N806

import numpy as np


def _prepare_colorarray(arr):
    """Check the shape of the array and convert to a floating point
    representation.

    This is heavily modified from scikit-image as the generalisations
    are not needed.
    """
    return np.asanyarray(arr, dtype=np.float32)


def rgb2luv(rgb):
    """RGB to CIE-Luv color space conversion.

    Parameters
    ----------
    rgb : (..., C=3, ...) array_like
        The image in RGB format. By default, the final dimension denotes
        channels.
    channel_axis : int, optional
        This parameter indicates which axis of the array corresponds to
        channels.

        .. versionadded:: 0.19
           ``channel_axis`` was added in 0.19.

    Returns
    -------
    out : (..., C=3, ...) ndarray
        The image in CIE Luv format. Same dimensions as input.

    Raises
    ------
    ValueError
        If `rgb` is not at least 2-D with shape (..., C=3, ...).

    Notes
    -----
    This function uses rgb2xyz and xyz2luv.

    References
    ----------
    .. [1] http://www.easyrgb.com/en/math.php
    .. [2] https://en.wikipedia.org/wiki/CIELUV
    """
    return xyz2luv(rgb2xyz(rgb))


def rgb2xyz(rgb):
    """RGB to XYZ color space conversion.

    Parameters
    ----------
    rgb : (..., C=3, ...) array_like
        The image in RGB format. By default, the final dimension denotes
        channels.
    channel_axis : int, optional
        This parameter indicates which axis of the array corresponds to
        channels.

        .. versionadded:: 0.19
           ``channel_axis`` was added in 0.19.

    Returns
    -------
    out : (..., C=3, ...) ndarray
        The image in XYZ format. Same dimensions as input.

    Raises
    ------
    ValueError
        If `rgb` is not at least 2-D with shape (..., C=3, ...).

    Notes
    -----
    The CIE XYZ color space is derived from the CIE RGB color space. Note
    however that this function converts from sRGB.

    References
    ----------
    .. [1] https://en.wikipedia.org/wiki/CIE_1931_color_space

    Examples
    --------
    >>> from skimage import data
    >>> img = data.astronaut()
    >>> img_xyz = rgb2xyz(img)
    """
    # Follow the algorithm from http://www.easyrgb.com/index.php
    # except we don't multiply/divide by 100 in the conversion
    arr = _prepare_colorarray(rgb).copy()
    mask = arr > 0.04045
    arr[mask] = np.power((arr[mask] + 0.055) / 1.055, 2.4)
    arr[~mask] /= 12.92
    return arr @ xyz_from_rgb.T.astype(arr.dtype)


def xyz2luv(xyz, illuminant="D65", observer="2"):
    """XYZ to CIE-Luv color space conversion.

    Parameters
    ----------
    xyz : (..., C=3, ...) array_like
        The image in XYZ format. By default, the final dimension denotes
        channels.
    illuminant : {"A", "B", "C", "D50", "D55", "D65", "D75", "E"}, optional
        The name of the illuminant (the function is NOT case sensitive).
    observer : {"2", "10", "R"}, optional
        The aperture angle of the observer.
    channel_axis : int, optional
        This parameter indicates which axis of the array corresponds to
        channels.

        .. versionadded:: 0.19
           ``channel_axis`` was added in 0.19.

    Returns
    -------
    out : (..., C=3, ...) ndarray
        The image in CIE-Luv format. Same dimensions as input.

    Raises
    ------
    ValueError
        If `xyz` is not at least 2-D with shape (..., C=3, ...).
    ValueError
        If either the illuminant or the observer angle are not supported or
        unknown.

    Notes
    -----
    By default XYZ conversion weights use observer=2A. Reference whitepoint
    for D65 Illuminant, with XYZ tristimulus values of ``(95.047, 100.,
    108.883)``. See function :func:`~.xyz_tristimulus_values` for a list of supported
    illuminants.

    References
    ----------
    .. [1] http://www.easyrgb.com/en/math.php
    .. [2] https://en.wikipedia.org/wiki/CIELUV

    Examples
    --------
    >>> from skimage import data
    >>> from skimage.color import rgb2xyz, xyz2luv
    >>> img = data.astronaut()
    >>> img_xyz = rgb2xyz(img)
    >>> img_luv = xyz2luv(img_xyz)
    """
    input_is_one_pixel = xyz.ndim == 1
    if input_is_one_pixel:
        xyz = xyz[np.newaxis, ...]

    arr = _prepare_colorarray(xyz)

    # extract channels
    x, y, z = arr[..., 0], arr[..., 1], arr[..., 2]

    eps = np.finfo(arr.dtype).eps

    # compute y_r and L
    xyz_ref_white = xyz_tristimulus_values(
        illuminant=illuminant, observer=observer, dtype=arr.dtype
    )
    L = y / xyz_ref_white[1]
    mask = L > 0.008856
    L[mask] = 116.0 * np.cbrt(L[mask]) - 16.0
    L[~mask] = 903.3 * L[~mask]

    uv_weights = np.array([1, 15, 3], dtype=arr.dtype)
    u0 = 4 * xyz_ref_white[0] / (uv_weights @ xyz_ref_white)
    v0 = 9 * xyz_ref_white[1] / (uv_weights @ xyz_ref_white)

    # u' and v' helper functions
    def fu(X, Y, Z):
        return (4.0 * X) / (X + 15.0 * Y + 3.0 * Z + eps)

    def fv(X, Y, Z):
        return (9.0 * Y) / (X + 15.0 * Y + 3.0 * Z + eps)

    # compute u and v using helper functions
    u = 13.0 * L * (fu(x, y, z) - u0)
    v = 13.0 * L * (fv(x, y, z) - v0)

    out = np.stack([L, u, v], axis=-1)

    if input_is_one_pixel:
        out = np.squeeze(out, axis=0)

    return out


# ---------------------------------------------------------------
# Matrices that define conversion between different color spaces
# ---------------------------------------------------------------

# From sRGB specification
xyz_from_rgb = np.array(
    [
        [0.412453, 0.357580, 0.180423],
        [0.212671, 0.715160, 0.072169],
        [0.019334, 0.119193, 0.950227],
    ]
)

# CIE XYZ tristimulus values of the illuminants, scaled to [0, 1]. For each illuminant I
# we have:
#
#   illuminant[I]['2'] corresponds to the CIE XYZ tristimulus values for the 2 degree
#   field of view.
#
#   illuminant[I]['10'] corresponds to the CIE XYZ tristimulus values for the 10 degree
#   field of view.
#
#   illuminant[I]['R'] corresponds to the CIE XYZ tristimulus values for R illuminants
#   in grDevices::convertColor
#
# The CIE XYZ tristimulus values are calculated from [1], using the formula:
#
#   X = x * ( Y / y )
#   Y = Y
#   Z = ( 1 - x - y ) * ( Y / y )
#
# where Y = 1. The only exception is the illuminant "D65" with aperture angle
# 2, whose coordinates are copied from 'lab_ref_white' for
# backward-compatibility reasons.
#
#     References
#    ----------
#    .. [1] https://en.wikipedia.org/wiki/Standard_illuminant

_illuminants = {
    "A": {
        "2": (1.098466069456375, 1, 0.3558228003436005),
        "10": (1.111420406956693, 1, 0.3519978321919493),
        "R": (1.098466069456375, 1, 0.3558228003436005),
    },
    "B": {
        "2": (0.9909274480248003, 1, 0.8531327322886154),
        "10": (0.9917777147717607, 1, 0.8434930535866175),
        "R": (0.9909274480248003, 1, 0.8531327322886154),
    },
    "C": {
        "2": (0.980705971659919, 1, 1.1822494939271255),
        "10": (0.9728569189782166, 1, 1.1614480488951577),
        "R": (0.980705971659919, 1, 1.1822494939271255),
    },
    "D50": {
        "2": (0.9642119944211994, 1, 0.8251882845188288),
        "10": (0.9672062750333777, 1, 0.8142801513128616),
        "R": (0.9639501491621826, 1, 0.8241280285499208),
    },
    "D55": {
        "2": (0.956797052643698, 1, 0.9214805860173273),
        "10": (0.9579665682254781, 1, 0.9092525159847462),
        "R": (0.9565317453467969, 1, 0.9202554587037198),
    },
    "D65": {
        "2": (0.95047, 1.0, 1.08883),  # This was: `lab_ref_white`
        "10": (0.94809667673716, 1, 1.0730513595166162),
        "R": (0.9532057125493769, 1, 1.0853843816469158),
    },
    "D75": {
        "2": (0.9497220898840717, 1, 1.226393520724154),
        "10": (0.9441713925645873, 1, 1.2064272211720228),
        "R": (0.9497220898840717, 1, 1.226393520724154),
    },
    "E": {"2": (1.0, 1.0, 1.0), "10": (1.0, 1.0, 1.0), "R": (1.0, 1.0, 1.0)},
}


def xyz_tristimulus_values(*, illuminant, observer, dtype=float):
    """Get the CIE XYZ tristimulus values.

    Given an illuminant and observer, this function returns the CIE XYZ tristimulus
    values [2]_ scaled such that :math:`Y = 1`.

    Parameters
    ----------
    illuminant : {"A", "B", "C", "D50", "D55", "D65", "D75", "E"}
        The name of the illuminant (the function is NOT case sensitive).
    observer : {"2", "10", "R"}
        One of: 2-degree observer, 10-degree observer, or 'R' observer as in
        R function ``grDevices::convertColor`` [3]_.
    dtype: dtype, optional
        Output data type.

    Returns
    -------
    values : array
        Array with 3 elements :math:`X, Y, Z` containing the CIE XYZ tristimulus values
        of the given illuminant.

    Raises
    ------
    ValueError
        If either the illuminant or the observer angle are not supported or
        unknown.

    References
    ----------
    .. [1] https://en.wikipedia.org/wiki/Standard_illuminant#White_points_of_standard_illuminants
    .. [2] https://en.wikipedia.org/wiki/CIE_1931_color_space#Meaning_of_X,_Y_and_Z
    .. [3] https://www.rdocumentation.org/packages/grDevices/versions/3.6.2/topics/convertColor

    Notes
    -----
    The CIE XYZ tristimulus values are calculated from :math:`x, y` [1]_, using the
    formula

    .. math:: X = x / y

    .. math:: Y = 1

    .. math:: Z = (1 - x - y) / y

    The only exception is the illuminant "D65" with aperture angle 2° for
    backward-compatibility reasons.

    Examples
    --------
    Get the CIE XYZ tristimulus values for a "D65" illuminant for a 10 degree field of
    view

    >>> xyz_tristimulus_values(illuminant="D65", observer="10")
    array([0.94809668, 1.        , 1.07305136])
    """
    illuminant = illuminant.upper()
    observer = observer.upper()
    try:
        return np.asarray(_illuminants[illuminant][observer], dtype=dtype)
    except KeyError as e:
        raise ValueError(
            f"Unknown illuminant/observer combination (`{illuminant}`, `{observer}`)"
        ) from e
