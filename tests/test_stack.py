"""Tests for the smart/fast stacking.

Currently these tests don't test the Thing itself, just surrounding functionality
"""

from typing import Optional
from random import randint

import pytest
import numpy as np
from hypothesis import given, strategies as st

from openflexure_microscope_server.things.autofocus import (
    StackParams,
    CaptureInfo,
    _get_capture_by_id,
    _get_capture_index_by_id,
)
from openflexure_microscope_server.scan_directories import IMAGE_REGEX

RANDOM_GENERATOR = np.random.default_rng()


def odd_integers(min_value=0, max_value=1000):
    """Return a hypothesis strategy for odd integers."""
    min_base = (min_value) // 2
    max_base = (max_value - 1) // 2
    # Ensure the range allows at least one odd number
    if min_base > max_base:
        return st.nothing()
    return st.integers(min_value=min_base, max_value=max_base).map(lambda x: 2 * x + 1)


def even_integers(min_value=0, max_value=1000):
    """Return a hypothesis strategy for even integers."""
    min_base = (min_value + 1) // 2
    max_base = (max_value) // 2
    # Ensure the range allows at least one even number
    if min_base > max_base:
        return st.nothing()
    return st.integers(min_value=min_base, max_value=max_base).map(lambda x: 2 * x)


@given(
    save_ims=odd_integers(min_value=0, max_value=10),
    extra_ims=even_integers(min_value=0, max_value=10),
)
def test_stack_params_validation(save_ims, extra_ims):
    """Tests specifically the validation on the image numbers

    save_ims is the number to save (must be odd and positive)
    extra_ims is how many more images there are in min_images_to_test than
    images_to_save. (even so that, min_images_to_test is odd and larger than
    images_to_save
    """
    StackParams(
        stack_dz=50,
        images_to_save=save_ims,
        min_images_to_test=save_ims + extra_ims,
        autofocus_dz=2000,
        images_dir="/this/is/fake",
        save_resolution=(1640, 1232),
    )


@given(
    save_ims=odd_integers(min_value=0, max_value=10),
    extra_ims=even_integers(min_value=-10, max_value=-1),
)
def test_stack_params_not_enough_test_images(save_ims, extra_ims):
    """Set the extra_ims negative so that min_images_to_test is smaller
    than images_to_save.

    For arguments see test_stack_params_validation
    """
    with pytest.raises(ValueError):
        StackParams(
            stack_dz=50,
            images_to_save=save_ims,
            min_images_to_test=save_ims + extra_ims,
            autofocus_dz=2000,
            images_dir="/this/is/fake",
            save_resolution=(1640, 1232),
        )


@given(
    save_ims=odd_integers(min_value=-10, max_value=-1),
    extra_ims=even_integers(min_value=0, max_value=10),
)
def test_stack_params_negative_images_to_save(save_ims, extra_ims):
    """save_ims is negative so images_to_save is negative, failing validation

    For arguments see test_stack_params_validation
    """
    with pytest.raises(ValueError):
        StackParams(
            stack_dz=50,
            images_to_save=save_ims,
            min_images_to_test=save_ims + extra_ims,
            autofocus_dz=2000,
            images_dir="/this/is/fake",
            save_resolution=(1640, 1232),
        )


@given(
    save_ims=odd_integers(min_value=0, max_value=10),
    extra_ims=odd_integers(min_value=0, max_value=10),
)
def test_even_min_images_to_test(save_ims, extra_ims):
    """extra_ims is odd so min_images_to_test is even, failing validation

    For arguments see test_stack_params_validation
    """
    with pytest.raises(ValueError):
        StackParams(
            stack_dz=50,
            images_to_save=save_ims,
            min_images_to_test=save_ims + extra_ims,
            autofocus_dz=2000,
            images_dir="/this/is/fake",
            save_resolution=(1640, 1232),
        )


@given(
    save_ims=even_integers(min_value=0, max_value=10),
    extra_ims=odd_integers(min_value=0, max_value=10),
)
def test_even_images_to_save(save_ims, extra_ims):
    """save_ims is even so images_to_save is even, failing validation

    For arguments see test_stack_params_validation
    """
    with pytest.raises(ValueError):
        StackParams(
            stack_dz=50,
            images_to_save=save_ims,
            min_images_to_test=save_ims + extra_ims,
            autofocus_dz=2000,
            images_dir="/this/is/fake",
            save_resolution=(1640, 1232),
        )


def test_computed_stack_params():
    """Test StackParams computed properties are as expected

    Not using hypothesis or we will just copy in the same formulas.
    """
    stack_parameters = StackParams(
        stack_dz=50,
        images_to_save=5,
        min_images_to_test=9,
        autofocus_dz=2000,
        images_dir="/this/is/fake",
        save_resolution=(1640, 1232),
    )

    assert stack_parameters.stack_z_range == 8 * 50

    assert stack_parameters.steps_undershoot == stack_parameters.img_undershoot * 50

    assert stack_parameters.max_images_to_test == 9 + 15

    sharpnesses = [50, 77, 234, 324, 390, 496, 569, 454, 333, 222, 178, 70]
    max_ind = np.argmax(sharpnesses)
    slice_to_save = stack_parameters.slice_to_save(max_ind)
    # Check the slice corresponds to the index for the 5 images centred on the sharpest
    assert sharpnesses[slice_to_save] == [390, 496, 569, 454, 333]

    # For a failed smart stack the slice may be truncated. Check it truncates correctly
    sharpnesses = [496, 569, 454, 333, 222, 178, 70, 69, 66, 50, 45, 40]
    max_ind = np.argmax(sharpnesses)
    slice_to_save = stack_parameters.slice_to_save(max_ind)
    # Check the slice corresponds to the index for the first 4 images
    assert sharpnesses[slice_to_save] == [496, 569, 454, 333]

    # And again for sharpest at the end
    sharpnesses = [13, 21, 26, 31, 39, 49, 50, 77, 234, 324, 390, 496, 569]
    max_ind = np.argmax(sharpnesses)
    slice_to_save = stack_parameters.slice_to_save(max_ind)
    # Check the slice corresponds to the index for the final 3 images
    assert sharpnesses[slice_to_save] == [390, 496, 569]


def random_capture(set_id: Optional[int] = None):
    """Create a capture with random values

    :param set_id: Optional, use to set a fixed id rather than a random one
    """
    buffer_id = set_id if set_id is not None else randint(0, 1000)
    return CaptureInfo(
        buffer_id=buffer_id,
        position={
            "x": randint(-100000, 100000),
            "y": randint(-100000, 100000),
            "z": randint(-100000, 100000),
        },
        sharpness=randint(0, 100000),
    )


def test_capture_filename_matches_regex():
    """For 100 random captures check the image always matches the regex"""
    for _ in range(100):
        assert IMAGE_REGEX.search(random_capture().filename)


@given(st.integers(min_value=0, max_value=5000))
def test_retrieval_of_captures(start):
    """For 20 random captures, check each can be retrieved correctly by id"""
    captures = [random_capture(start + i) for i in range(20)]

    for i, capture in enumerate(captures):
        buffer_id = capture.buffer_id
        assert _get_capture_index_by_id(captures, buffer_id) == i
        assert _get_capture_by_id(captures, buffer_id) is capture

    # Check errors are raised when supplying ids that aren't in the list
    with pytest.raises(ValueError):
        _get_capture_index_by_id(captures, start - 1)
    with pytest.raises(ValueError):
        _get_capture_index_by_id(captures, start + 21)
    with pytest.raises(ValueError):
        _get_capture_by_id(captures, start - 1)
    with pytest.raises(ValueError):
        _get_capture_by_id(captures, start + 21)
