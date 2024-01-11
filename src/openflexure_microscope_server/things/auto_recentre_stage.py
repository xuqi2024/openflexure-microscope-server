import numpy as np
import logging
import time

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.decorators import thing_action
from labthings_sangaboard import SangaboardThing
from labthings_picamera2.thing import StreamingPiCamera2
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper

StageDep = direct_thing_client_dependency(SangaboardThing, "/stage/")
CamDep = direct_thing_client_dependency(StreamingPiCamera2, "/camera/")
CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")


def turningpoints(lst):
    dx = np.diff(lst)
    return dx[1:] * dx[:-1] < 0


def unpack_autofocus(scan_data):
    """Extract z, sharpness data from a move_and_measure call"""
    scan_data = dict(scan_data)
    jpeg_times = scan_data["jpeg_times"]
    jpeg_sizes = scan_data["jpeg_sizes"]
    jpeg_sizes_MB = [x / 10**3 for x in jpeg_sizes]
    stage_times = scan_data["stage_times"]
    stage_positions = scan_data["stage_positions"]
    stage_height = [pos["z"] for pos in stage_positions]

    jpeg_heights = np.interp(jpeg_times, stage_times, stage_height)

    turning = np.where(turningpoints(jpeg_heights))[0] + 1

    return jpeg_heights[turning[0] : turning[1]], jpeg_sizes_MB[turning[0] : turning[1]]


class RecentringThing(Thing):
    @thing_action
    def looping_autofocus(self, autofocus: AutofocusDep, stage: StageDep, dz=2000):
        """Repeatedly autofocus the stage until it looks focused.
        
        This action will run the `fast_autofocus` action until it settles on a point
        in the middle 3/5 of its range. Such logic can be helpful if the microscope
        is close to focus, but not quite within `dz/2`. It will attempt to autofocus
        up to 10 times.
        """
        repeat = True
        attempts = 0
        while repeat and attempts < 10:
            height_min = stage.position["z"] - dz / 2
            height_max = stage.position["z"] + dz / 2
            data = autofocus.fast_autofocus(dz=dz)
            heights, _ = unpack_autofocus(data)
            time.sleep(0.3)
            # TODO: max heights seems badly wrong! Something about turning?
            if (
                stage.position["z"] - height_min < dz / 5
                or height_max - stage.position["z"] < dz / 5
            ):
                print(heights)
                attempts += 1
            else:
                repeat = False

    @thing_action
    def recentre(
        self,
        autofocus: AutofocusDep,
        stage: StageDep,
        max_steps=15,
        lateral_distance=5000,
    ):
        """Recentre the stage, based on the focal plane

        Autofocuses at multiple points around the sample to
        find the overall maximum (or minimum) height, which
        corresponds to the centre of the stage. This exploits the
        fact that the OpenFlexure stage moves in an arc, i.e. its
        height will vary with X and Y. The point where the variation
        of Z with X and Y motion is smallest is the centre of its 
        XY travel. This routine moves in X and Y, monitoring the
        Z value of the focal plane, and attempts to find the point
        where Z does not vary with X and Y, which is where it stops.

        max_steps: The maximum number of moves in x or y before
        aborting due to a poorly positioned stage or hard to focus
        sample

        lateral_distance: The xy distance between areas to check.
        Below 3000 becomes less reliable, as focus shouldn't shift
        much between these sites, making the procedure more sensitive
        to noise or a failed autofocus.
        """

        max_steps = 20
        dx = lateral_distance

        centre = list(stage.position.values())

        # A list of all the positions we've focused
        focused_pos = [[], []]

        self.looping_autofocus(autofocus, stage)

        for direction in [0, 1]:
            # Start off with the current position, and moving in the positive direction
            focused_pos[direction] = [list(stage.position.values())]
            moves = +1

            stage.move_absolute(x=centre[0], y=centre[1], z=centre[2])
            steps = 0
            all_heights = []

            # We'll run this for x, then y
            while True:
                # If we're moving in the positive direction, we want the highest point
                # Otherwise, we want the lowest
                if moves > 0:
                    starting_point = np.max(
                        np.array(focused_pos[direction])[:, direction]
                    )
                else:
                    starting_point = np.min(
                        np.array(focused_pos[direction])[:, direction]
                    )

                # Next location is an extra move in the direction we want
                destination = centre
                destination[direction] = starting_point + moves * dx
                stage.move_absolute(
                    x=int(destination[0]), y=int(destination[1]), z=destination[2]
                )
                self.looping_autofocus(autofocus, stage)
                position = list(stage.position.values())
                focused_pos[direction].append(position)

                steps += 1
                if steps > max_steps:
                    logging.warning(
                        "Couldn't find a suitable position. Roughly centre the stage and check your sample is suitable for autofocus"
                    )
                    break

                if len(focused_pos[direction]) >= 4:
                    all_heights = [x[2] for x in focused_pos[direction]]
                    direction_index = [x[direction] for x in focused_pos[direction]]

                    sorted_all_heights = [
                        x for y, x in sorted(zip(direction_index, all_heights))
                    ]

                    sorted_lateral = sorted(direction_index)
                    quad_fit = np.polyfit(sorted_lateral, sorted_all_heights, 2)
                    quad_fit_func = np.poly1d(quad_fit)

                    turning = quad_fit_func.deriv()

                    turning_loc = -turning[0] / (turning[1])

                    test_sorted_all_heights = [i * np.sign(quad_fit[0]) for i in sorted_all_heights]

                    if (
                        np.argmin(test_sorted_all_heights) != 0
                        and np.argmin(test_sorted_all_heights) != len(all_heights) - 1
                    ):
                        logging.info(
                            f"Breaking because the turning point is at {np.argmin(test_sorted_all_heights)} in the list"
                        )
                        # plt.plot(sorted_lateral, sorted_all_heights,'.')
                        # plt.plot(sorted_lateral, quad_fit_func(sorted_lateral))
                        # plt.show()
                        break
                    else:
                        if turning_loc < np.min(sorted_lateral):
                            moves = -1
                        elif turning_loc > np.max(sorted_lateral):
                            moves = 1
                        else:
                            # plt.plot(sorted_lateral, sorted_all_heights,'.')
                            # plt.plot(sorted_lateral, quad_fit_func(sorted_lateral))
                            # plt.show()
                            pass

            # Centre value is replaced by the maximum value recorded in that axis
            centre[direction] = focused_pos[direction][np.argmax(all_heights)][
                direction
            ]
            stage.move_absolute(x=centre[0], y=centre[1], z=centre[2])
            self.looping_autofocus(autofocus, stage)

        logging.info(f"Centre of ROM is at {centre, stage.position['z']} \n")

        return focused_pos
