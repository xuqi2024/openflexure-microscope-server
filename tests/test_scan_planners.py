import pytest
from openflexure_microscope_server import scan_planners
from copy import copy


def test_enforce_xy_tuple():
    bad_len_vals = [[1], [], (1,), (2, 4, 4), [1, 4, 5, 7]]
    bad_type_vals = ["hi", 1, {"this": "that"}, {1, 2}]
    for value in bad_len_vals + bad_type_vals:
        with pytest.raises(ValueError):
            scan_planners.enforce_xy_tuple(value)

    assert (1, 6) == scan_planners.enforce_xy_tuple((1, 6))
    assert (1, 6) == scan_planners.enforce_xy_tuple([1, 6])


def test_enforce_xyz_tuple():
    bad_len_vals = [[1], [], (1,), (2, 4), [1, 4, 5, 7]]
    bad_type_vals = ["hi!", 1, {"this": "that"}, {1, 2, 3}]
    for value in bad_len_vals + bad_type_vals:
        with pytest.raises(ValueError):
            scan_planners.enforce_xyz_tuple(value)

    assert (1, 6, 2) == scan_planners.enforce_xyz_tuple((1, 6, 2))
    assert (1, 6, 6) == scan_planners.enforce_xyz_tuple([1, 6, 6])


def test_v_basic_smart_spiral():
    intial_position = (100, 50)
    planner_settings = {"dx": 50, "dy": 50, "max_dist": 10000}
    planner = scan_planners.SmartSpiral(
        intial_position=intial_position, planner_settings=planner_settings
    )
    # Create a planner it shouldn't start complete
    assert not planner.scan_complete
    # When we start it should want to stay in the inital pos and have
    # no z_estimate
    xy_pos, z_pos = planner.get_next_location_and_z_estimate()
    assert xy_pos == intial_position
    assert z_pos is None

    # Try to make imaged with only xy_position
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


def test_bad_smart_spiral_settings():
    intial_position = (100, 50)
    planner_settings = {"dx": 50, "dy": 50, "max_dist": 10000}
    with pytest.raises(KeyError):
        keys = ["dx", "dy", "max_dist"]
        for delkey in keys:
            bad_planner_settings = copy(planner_settings)
            del bad_planner_settings[delkey]
            scan_planners.SmartSpiral(
                intial_position=intial_position, planner_settings=bad_planner_settings
            )
    with pytest.raises(ValueError):
        keys = ["dx", "dy", "max_dist"]
        for badkey in keys:
            bad_planner_settings = copy(planner_settings)
            bad_planner_settings[badkey] = "I can't be converted to an int"
            scan_planners.SmartSpiral(
                intial_position=intial_position, planner_settings=bad_planner_settings
            )


def test__smart_spiral_next_pos():
    intial_position = (100, 50)
    planner_settings = {"dx": 50, "dy": 50, "max_dist": 10000}
    planner = scan_planners.SmartSpiral(
        intial_position=intial_position, planner_settings=planner_settings
    )
    # Create a planner it shouldn't start complete
    assert not planner.scan_complete
    # When we start it should want to stay in the inital pos and have
    # no z_estimate
    xy_pos, z_pos = planner.get_next_location_and_z_estimate()
    assert xy_pos == intial_position
    assert z_pos is None
    z_focus = 10
    xyz_pos = (xy_pos[0], xy_pos[1], z_focus)
    # if we mark this position as visited and imaged
    planner.mark_location_visited(xyz_pos, imaged=True, focused=True)

    # scan is not complete
    assert not planner.scan_complete

    # Lists should have updated to add the position to histories
    assert xyz_pos in planner._imaged_locations
    assert xyz_pos in planner._focused_locations
    assert xy_pos in planner._path_history

    # remove from planned
    assert xy_pos not in planner._remaining_locations

    # Add 4 new points to planned
    assert (100, 0) in planner._remaining_locations
    assert (100, 100) in planner._remaining_locations
    assert (150, 50) in planner._remaining_locations
    assert (50, 50) in planner._remaining_locations
    assert len(planner._remaining_locations) == 4

    # Now the next location is update
    xy_pos, z_pos = planner.get_next_location_and_z_estimate()
    # move in negative x-dir first
    assert xy_pos == (50, 50)
    assert z_pos is z_focus
