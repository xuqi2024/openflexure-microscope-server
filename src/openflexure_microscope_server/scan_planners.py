"""
This module contains functionality for planning a scan route

A scan route can be planned by a ScanPlanner class currently there
is only one type the SmartSpiral. More can be added using by
subclassing the ScanPlanner
"""

from typing import TypeAlias, Optional
import logging
from copy import copy

import numpy as np

LOGGER = logging.getLogger(__name__)

XYPos: TypeAlias = tuple[int, int]
XYZPos: TypeAlias = tuple[int, int, int]
XYPosList: TypeAlias = list[XYPos]
XYZPosList: TypeAlias = list[XYZPos]


def enforce_xy_tuple(value: XYPos) -> XYPos:
    """
    Used for enforcing that an input is a tuple and is the correct length
    """
    if not isinstance(value, (list, tuple)):
        raise ValueError("2 value tuple expected")
    if not len(value) == 2:
        raise ValueError("2 value tuple expected")
    if isinstance(value, list):
        return tuple(value)
    return value


def enforce_xyz_tuple(value: XYZPos) -> XYZPos:
    """
    Used for enforcing that an input is a tuple and is the correct length
    """
    if not isinstance(value, (list, tuple)):
        raise ValueError("3 value tuple expected")
    if not len(value) == 3:
        raise ValueError("3 value tuple expected")
    if isinstance(value, list):
        return tuple(value)
    return value


class ScanPlanner:
    """
    A base class for a scan planner.

    This should never be used directly for a scan, it should be subclassed.

    Each subclass should implement at least the methods with NotImplementedError
    set:
    * _parse() - to parse the planner_settings dictionary, saving values to class
        variables
    * _intial_location_list() - Sets the list of locations for the scan to follow

    For a simple scan pattern this should be sufficent. For more complex ones that
    dynanically adjust the path it is suggested to override `mark_location_visited()`
    calling `super().mark_location_visited()` at the start of the method so that all
    locations are adjusted.

    When subclassing be sure to use enforce_xy_tuple and enforce_xyz_tuple on any user
    data before running
    """

    def __init__(self, intial_position: XYPos, planner_settings: Optional[dict] = None):
        """
        Set up lists for the path planning, and scan history.
        """

        self._initial_position = enforce_xy_tuple(intial_position)
        self._parse(planner_settings)

        # The remaining (x,y) locations to scan
        # (This was `path` before refactoring from the long `sample_scan` code)
        self._remaining_locations: XYPosList = self._intial_location_list()

        # This holds a list of all (x,y,z) locations where images were taken
        # this may not be equivalent to the x,y poistions ins self._path_history
        # if background detect is used
        # (This was not used in the `sample_scan` code)
        self._imaged_locations: XYZPosList = []

        # This holds a list of all (x,y,z) locations where autofocus was successful
        # (This was `focused_path` before refactoring from the long `sample_scan` code)
        self._focused_locations: XYZPosList = []

        # This holds a list of all  x,y locations visited in order since the start
        # (This was `true_path` before refactoring from the long `sample_scan` code
        # previously it had  z set, but if we don't take an image, not z is needed and
        # it slows other checks)
        self._path_history: XYPosList = []

    @property
    def scan_complete(self) -> bool:
        """
        Return True if there are no locations left to scan.
        """
        return not self._remaining_locations

    @property
    def remaining_locations(self) -> XYPosList:
        """
        Property to access a copy of the remaining_locations
        """
        return copy(self._remaining_locations)

    @property
    def imaged_locations(self) -> XYZPosList:
        """
        Property to access a copy of the imaged_locations
        """
        return copy(self._imaged_locations)

    @property
    def focused_locations(self) -> XYZPosList:
        """
        Property to access a copy of the focused_locations
        """
        return copy(self._focused_locations)

    @property
    def path_history(self) -> XYPosList:
        """
        Property to access a copy of the path_history
        """
        return copy(self._path_history)

    def _parse(self, planner_settings: Optional[dict] = None) -> None:
        """
        Parse any settings sent to this planner and store them if needed.
        """
        raise NotImplementedError("Did you call the ScanPlanner base class?")

    def _intial_location_list(self) -> XYPosList:
        """
        Called on initalisation. Sets the initial list of locations for this scan planner

        For a simple grid scan/snake scan this would be all locations to move to.

        Note for implementation that this _must_ contain (x,y) tuples, not [x, y]
        lists or matching errors could occur.
        """
        raise NotImplementedError("Did you call the ScanPlanner base class?")

    def position_visited(self, position: XYPos) -> bool:
        """
        Return True if input xy position has been visited before
        """
        # Ensure tuple for correct matching!
        return tuple(position) in self._path_history

    def position_planned(self, position: XYPos) -> bool:
        """
        Return True if input xy position is planned
        """
        # Ensure tuple for correct matching!
        return tuple(position) in self._remaining_locations

    def get_next_location_and_z_estimate(self) -> tuple[XYPos, Optional[int]]:
        """
        Return the next location to scan, and the estimated z-position
        for this location.

        Note z-position may be None! This indicates that the current z, position
        should be used.
        """
        if self.scan_complete:
            raise RuntimeError("Can't get next position, scan is complete")

        next_location = self._remaining_locations[0]

        # If focussed locations exist return closest location, favouring most recent
        closest_pos = self.closest_focus_site(next_location)
        if closest_pos is None:
            z = None
        else:
            z = closest_pos[2]

        return next_location, z

    def closest_focus_site(self, xy_pos: XYPos) -> Optional[XYZPos]:
        """
        Return the xyz position of the closest site where focus was achieved
        to the input xy_position, with the most recently taken image returned in
        the case of a tie

        Returns None if there if no focussed locations are present
        """
        if not self._focused_locations:
            return None

        # must be float64 (double precision) to deal with the huge numbers involved!
        current_pos = np.array(xy_pos, dtype="float64")
        path_pos = np.array(self._focused_locations, dtype="float64")[:, :2]

        # Use linalg.norm to calculate the direct distance bweween the points
        # Note linalg.norm always uses float64
        dists = np.linalg.norm((path_pos - current_pos), axis=1)

        # Get indices of all minima.
        # Note np.where always returns a tuple of arrays, hence the trailing [0]
        indices = np.where(dists == np.min(dists))[0]

        # The last index is most recent
        return self._focused_locations[indices[-1]]

    def mark_location_visited(
        self, xyz_pos: XYZPos, imaged: bool, focused: bool
    ) -> None:
        """
        Mark the location as visited

        Args:
            xyz_pos: the x_y_z position
            imaged: true if an image was taken, false if not (due to background detect)
            focused: true if autofocus completed successfully
        """
        # ensure is tuple!
        xyz_pos = enforce_xyz_tuple(xyz_pos)
        xy_pos = xyz_pos[:2]

        # Remove the expected position from the remaining locations list
        # and check it's correct
        expected_pos = tuple(self._remaining_locations.pop(0))
        if xy_pos != expected_pos:
            raise RuntimeError("Wrong scan location visited!")

        # Append xy position for path_history
        self._path_history.append(xy_pos)
        # And full x,y,z for imaged and foucsed if appropriate
        if imaged:
            self._imaged_locations.append(xyz_pos)
        if focused:
            self._focused_locations.append(xyz_pos)


class SmartSpiral(ScanPlanner):
    """
    This is a smart spiral scan that spirals out from the centre, but prioritises
    short moves over rigidly sticking to minimising radius from the centre of the
    scan.

    Each time and image is taken the four neighbouring images are added
    to the list of poisitions to image (unless they are already listed or
    tried). However if a location is not imaged due no sample being detected
    then neibouring positions are not imaged.

    The next image taken is the closes to the centre (considering the largest
    of vertical or horizontal distance), ties are broken by the distance from
    the current position.
    """

    _max_dist: int = 0
    _dx: int = 0
    _dy: int = 0

    def _parse(self, planner_settings: Optional[dict] = None) -> None:
        """
        Parse SmartSpiral Settings. This should be a dictionary

        "dx" - the movement size in x
        "dy" - the movement size in y
        "max_dist" - The maximum distance to a location can be from the centre.
        """

        expected_keys = ["max_dist", "dx", "dy"]
        invalid_msg = "SmartSpiral requires a planner_settings dictionary with keys: "
        if not planner_settings:
            raise ValueError(invalid_msg + ",".join(expected_keys))
        if not all(keys in planner_settings for keys in expected_keys):
            raise KeyError(invalid_msg + ",".join(expected_keys))

        self._dx = int(planner_settings["dx"])
        self._dy = int(planner_settings["dy"])
        self._max_dist = int(planner_settings["max_dist"])

    def _intial_location_list(self) -> XYPosList:
        """
        Called on initalisation. Sets the initial list of locations for this scan planner

        For smart spiral this is just the first point
        """
        return [self._initial_position]

    def mark_location_visited(
        self, xyz_pos: XYZPos, imaged: bool = True, focused: bool = True
    ) -> None:
        """
        Mark the location as visited. Adjust extra positions accordingly

        Args:
            xyz_pos: the x_y_z position
            imaged: true if an image was taken, false if not (due to background detect)
            focused: true if autofocus completed successfully
        """
        # First call the base class to update the positions
        super().mark_location_visited(xyz_pos, imaged, focused)

        xy_pos = enforce_xy_tuple(xyz_pos[:2])
        if imaged:
            self._add_surrounding_positions(xy_pos)
        self._re_sort_remaining_locations(xy_pos)

    def _add_surrounding_positions(self, xy_pos: XYPos) -> None:
        """
        This adds the surrounding (4 point connectivity) positions
        to the remaining locations if they are not too far away or
        already planned or already visited
        """
        new_positions = [
            (xy_pos[0] - self._dx, xy_pos[1]),
            (xy_pos[0] + self._dx, xy_pos[1]),
            (xy_pos[0], xy_pos[1] - self._dy),
            (xy_pos[0], xy_pos[1] + self._dy),
        ]

        for new_pos in new_positions:
            # Skip position if already planned or visited
            if self.position_planned(new_pos) or self.position_visited(new_pos):
                continue

            dist = distance_between(new_pos, self._initial_position)
            if dist > self._max_dist:
                LOGGER.debug("Rejected moving to %s as it is out of range", new_pos)
                continue
            self._remaining_locations.append(new_pos)

    def _re_sort_remaining_locations(self, current_pos: XYPos) -> None:
        """
        Sort the remaining positions besed on the current location
        """

        # Defined rather than use a lambda for readability
        def sort_key(pos):
            return (
                self.moves_between(current_pos, pos),
                self.moves_between(self._initial_position, pos),
                distance_between(current_pos, pos),
            )

        self._remaining_locations.sort(key=sort_key)

    def moves_between(
        self,
        starting_pos: XYPos | np.ndarray,
        ending_pos: XYPos | np.ndarray,
    ) -> float:
        """
        Return the number of moves between two xy positions in the x or y direction
        whichever is largest

        Args:
        starting_pos: the position to measure from
        ending_pos: the position to measure to
        """
        move_size = np.array([self._dx, self._dy])

        starting_pos = np.array(starting_pos, dtype="float64")
        ending_pos = np.array(ending_pos, dtype="float64")

        displacement_in_moves = (ending_pos - starting_pos) / move_size

        return np.max(np.abs(displacement_in_moves))


def distance_between(
    current_pos: XYPos | np.ndarray, next_pos: XYPos | np.ndarray
) -> float:
    """
    Calculate the distance between the two xy positions

    This was previously called `distance_to_site`
    """
    next_pos = np.array(next_pos, dtype="float64")
    current_pos = np.array(current_pos, dtype="float64")
    return float(np.linalg.norm(next_pos - current_pos))
