"""Test the scan planning algorithms of the Microscope.

As well as low level function by function tests, this test suite also provides tests
that simulate scanning a sample, checking that the expected path is followed.
"""

import pytest
from copy import copy

from openflexure_microscope_server import scan_planners
from .utilities import scan_test_helpers


def test_enforce_xy_tuple():
    """Check that 2 value tuples (or ValueErrors) are always returned."""
    bad_len_vals = [[1], [], (1,), (2, 4, 4), [1, 4, 5, 7]]
    bad_type_vals = ["hi", 1, {"this": "that"}, {1, 2}]
    for value in bad_len_vals + bad_type_vals:
        with pytest.raises(ValueError):
            scan_planners.enforce_xy_tuple(value)

    assert (1, 6) == scan_planners.enforce_xy_tuple((1, 6))
    assert (1, 6) == scan_planners.enforce_xy_tuple([1, 6])


def test_enforce_xyz_tuple():
    """Check that 3 value tuples (or ValueErrors) are always returned."""
    bad_len_vals = [[1], [], (1,), (2, 4), [1, 4, 5, 7]]
    bad_type_vals = ["hi!", 1, {"this": "that"}, {1, 2, 3}]
    for value in bad_len_vals + bad_type_vals:
        with pytest.raises(ValueError):
            scan_planners.enforce_xyz_tuple(value)

    assert (1, 6, 2) == scan_planners.enforce_xyz_tuple((1, 6, 2))
    assert (1, 6, 6) == scan_planners.enforce_xyz_tuple([1, 6, 6])


def test_base_class_not_implemented():
    """Check NotImplementedError is raised when initialising ScanPlanner directly."""
    intial_position = (100, 50)
    with pytest.raises(NotImplementedError):
        scan_planners.ScanPlanner(intial_position=intial_position)


def test_v_basic_smart_spiral():
    """Check that a SmartSpiral where the first image is not sample completes."""
    intial_position = (100, 50)
    planner_settings = {"dx": 50, "dy": 50, "max_dist": 10000}
    planner = scan_planners.SmartSpiral(
        intial_position=intial_position, planner_settings=planner_settings
    )
    # Create a planner. It shouldn't be complete.
    assert not planner.scan_complete
    # When we start it should want to stay in the inital pos and have
    # no z_estimate
    xy_pos, z_pos = planner.get_next_location_and_z_estimate()
    assert xy_pos == intial_position
    assert z_pos is None

    # Try to mark location as imaged with only xy_position
    with pytest.raises(ValueError):
        planner.mark_location_visited(xy_pos, imaged=False, focused=False)
    # scan still not complete
    assert not planner.scan_complete
    # if we mark this position as visited but not imaged
    planner.mark_location_visited(
        (xy_pos[0], xy_pos[1], 10), imaged=False, focused=False
    )
    # scan is now complete
    assert planner.scan_complete

    # if scan is complete, asking for the next location returns an error
    with pytest.raises(RuntimeError):
        planner.get_next_location_and_z_estimate()


def test_bad_smart_spiral_settings():
    """Check that KeyError is raised when SmartSpiral is given bad settings."""
    intial_position = (100, 50)

    # Class init should raise error if no planner_settings dictionary set
    with pytest.raises(ValueError):
        scan_planners.SmartSpiral(intial_position=intial_position)

    planner_settings = {"dx": 50, "dy": 50, "max_dist": 10000}
    keys = ["dx", "dy", "max_dist"]

    # Class init should raise error if planner_settings is missing any key
    for delkey in keys:
        bad_planner_settings = copy(planner_settings)
        del bad_planner_settings[delkey]
        with pytest.raises(KeyError):
            scan_planners.SmartSpiral(
                intial_position=intial_position, planner_settings=bad_planner_settings
            )

    # Class init should raise error if planner_settings if any value can't be cast
    # to int
    keys = ["dx", "dy", "max_dist"]
    for badkey in keys:
        bad_planner_settings = copy(planner_settings)
        bad_planner_settings[badkey] = "I can't be converted to an int"
        with pytest.raises(ValueError):
            scan_planners.SmartSpiral(
                intial_position=intial_position, planner_settings=bad_planner_settings
            )


def test_smart_spiral_first_few_pos():
    """Test for correct data addition during initial scan positions.

    This is a very long test, not strictly a "unit" test. It checks step by step
    that data is added correctly for the first few positions in a scan. It is
    intended to catch basic issues if the algorithm is updated.
    """
    intial_position = (100, 50)
    planner_settings = {"dx": 50, "dy": 50, "max_dist": 10000}
    # Create a planner
    planner = scan_planners.SmartSpiral(
        intial_position=intial_position, planner_settings=planner_settings
    )
    # it shouldn't start complete
    assert not planner.scan_complete
    # When we start it should want to stay in the inital pos and have
    # no z_estimate
    xy_pos1, z_pos1 = planner.get_next_location_and_z_estimate()
    assert xy_pos1 == intial_position
    assert z_pos1 is None
    # Set a focus value
    z_focus = 10
    xyz_pos1 = (xy_pos1[0], xy_pos1[1], z_focus)
    # if we mark this position as visited, imaged, and focused
    planner.mark_location_visited(xyz_pos1, imaged=True, focused=True)

    # scan is not complete
    assert not planner.scan_complete

    # Lists should have updated to add the position to histories
    assert xyz_pos1 in planner.imaged_locations
    assert xyz_pos1 in planner.focused_locations
    assert xy_pos1 in planner.path_history

    # remove from planned
    assert xy_pos1 not in planner.remaining_locations

    # Add 4 new points to planned
    assert (100, 0) in planner.remaining_locations
    assert (100, 100) in planner.remaining_locations
    assert (150, 50) in planner.remaining_locations
    assert (50, 50) in planner.remaining_locations
    assert len(planner.remaining_locations) == 4

    # Now the next location is updated
    xy_pos2, z_pos2 = planner.get_next_location_and_z_estimate()
    # move in negative x-dir first
    assert xy_pos2 == (50, 50)
    # Focus set from closest point
    assert z_pos2 is z_focus

    xyz_pos2 = (xy_pos2[0], xy_pos2[1], z_focus)
    # if we mark this position as visited, imaged, and NOT focused
    planner.mark_location_visited(xyz_pos2, imaged=True, focused=False)

    # Check this position remove from planned
    assert xy_pos2 not in planner.remaining_locations
    # Check original position not re-added
    assert xy_pos1 not in planner.remaining_locations

    # 3 old points still planned
    assert (100, 0) in planner.remaining_locations
    assert (100, 100) in planner.remaining_locations
    assert (150, 50) in planner.remaining_locations
    # Add 3 new points to planned
    assert (0, 50) in planner.remaining_locations
    assert (50, 100) in planner.remaining_locations
    assert (50, 0) in planner.remaining_locations
    assert len(planner.remaining_locations) == 6

    # Now the next location is updated
    xy_pos3, z_pos3 = planner.get_next_location_and_z_estimate()
    # move in negative y-dir first next
    assert xy_pos3 == (50, 0)
    # Focus still set as before
    assert z_pos3 is z_focus
    # Check that the closest focus site to pos3 is pos 1 as
    # pos 2 is not focussed
    assert planner.closest_focus_site(xy_pos3) == xyz_pos1

    new_z_focus = 20
    xyz_pos3 = (xy_pos3[0], xy_pos3[1], new_z_focus)
    # Finally check that if this is focused...
    planner.mark_location_visited(xyz_pos3, imaged=True, focused=True)
    # ... then the new 4th point ...
    xy_pos4, z_pos4 = planner.get_next_location_and_z_estimate()
    # ...(100, 0)...
    assert xy_pos4 == (100, 0)
    # ... and it should get its focus from the lowest neighbouring point
    assert z_pos4 is z_focus
    assert planner.closest_focus_site(xy_pos4) == xyz_pos3


def test_smart_spiral_stops_on_max_dist():
    """Test that if max distance is reached smart spiral really does stop."""
    intial_position = (0, 0)
    planner_settings = {"dx": 100, "dy": 100, "max_dist": 1000}
    # Create a planner
    planner = scan_planners.SmartSpiral(
        intial_position=intial_position, planner_settings=planner_settings
    )
    while not planner.scan_complete:
        xy_pos, _ = planner.get_next_location_and_z_estimate()
        xyz_pos = (xy_pos[0], xy_pos[1], 0)
        planner.mark_location_visited(xyz_pos, imaged=True, focused=True)

    # Estimate of radius = 10 scans, pir^2 = 314 images. In reality it works out as
    # 317
    assert len(planner.path_history) == 317


def test_mark_wrong_location():
    """Check that an error is raised if a scan marks the wrong location as visited."""
    intial_position = (100, 50)
    planner_settings = {"dx": 50, "dy": 50, "max_dist": 10000}
    # Create a planner
    planner = scan_planners.SmartSpiral(
        intial_position=intial_position, planner_settings=planner_settings
    )

    xy_pos, _ = planner.get_next_location_and_z_estimate()
    # Trying to mark the wrong location as visited raises error
    wrong_xyz_pos = (xy_pos[0] + 1, xy_pos[1], 0)
    with pytest.raises(RuntimeError):
        planner.mark_location_visited(wrong_xyz_pos, imaged=True, focused=True)


def test_closest_focus_wth_large_numbers():
    """Tests to check that everything works well with huge numbers of steps.

    The number of steps gets very large on the micorscope. But most of the tests
    above use smaller numbers for clarity.
    """
    intial_position = (0, 0)
    # Set this up, but we won't use the settings
    planner_settings = {"dx": 10000, "dy": 10000, "max_dist": 100000}
    # Create a planner
    planner = scan_planners.SmartSpiral(
        intial_position=intial_position, planner_settings=planner_settings
    )
    # Directly overwrite the private focussed locations list for test

    # For two points 1m points away it should choose the last as they are equal
    planner._focused_locations = [(1000000, 0, 0), (0, 1000000, 0)]
    assert planner.closest_focus_site((0, 0)) == (0, 1000000, 0)
    # Try similar
    planner._focused_locations = [(1234567, 0, 0), (-1234567, 0, 0)]
    assert planner.closest_focus_site((0, 0)) == (-1234567, 0, 0)

    # Make the first point 1 step closer
    planner._focused_locations = [(1234566, 0, 0), (-1234567, 0, 0)]
    assert planner.closest_focus_site((0, 0)) == (1234566, 0, 0)


def test_example_smart_spiral():
    """Test the smart spiral scan algorithm on the different sample types.

    The sample types:

    * ``regular``
    * ``lobed``
    * ``core"``

    These are defined in scan_test_helpers.load_sample_points

    This will fail if the locations or path between locations visited has changed
    for any of the samples listed.
    """
    example_samples = [
        "regular",
        "lobed",
        "core",
    ]
    for sample_name in example_samples:
        _, planner = scan_test_helpers.example_smart_spiral(sample_name)
        expected_planner = (
            scan_test_helpers.get_expected_result_for_example_smart_spiral(sample_name)
        )
        assert planner.path_history == expected_planner.path_history
        assert planner.imaged_locations == expected_planner.imaged_locations
