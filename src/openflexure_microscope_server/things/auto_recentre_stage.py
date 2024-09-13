import numpy as np
import logging
import cv2
import json
from PIL import Image
import time
from typing import Annotated, Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.invocation import CancelHook, InvocationLogger, InvocationCancelledError
from labthings_fastapi.decorators import thing_action, thing_property
from labthings_sangaboard import SangaboardThing
from labthings_picamera2.thing import StreamingPiCamera2
from labthings_fastapi.types.numpy import NDArray, denumpify, DenumpifyingDict
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper

StageDep = direct_thing_client_dependency(SangaboardThing, "/stage/")
CamDep = direct_thing_client_dependency(StreamingPiCamera2, "/camera/")
CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")

class RangeofMotionThing(Thing):
    @thing_action
    def measure_rom(
        self,
        autofocus: AutofocusDep,
        stage: StageDep,
        cam: CamDep,
        csm: CSMDep,
        cancel: CancelHook,
        logger: InvocationLogger
    ):
        """Recentre the stage, based on the focal plane
        Measure the range of motion of the stage, by moving along
        the postive and negative x and y directions by less than 
        one full image, checking the correlation between images,
        and breaking if it appears to have undershot.
            """
        starting_position = list(stage.position.values())

        try:
            logger.info("Using the stage to measure the range of motion")

            lateral_offset = 60
            stream_resolution = cam.stream_resolution

            step_sizes = {
                'x' : (lateral_offset / 100) * stream_resolution[0],
                'y' : (lateral_offset / 100) * stream_resolution[1],
            }

            minimum_offset = {
                'x' : int(step_sizes['x'] * 0.8),
                'y' : int(step_sizes['y'] * 0.8),
            }

            this_step_size = {}

            try:
                pixel_um = micat.last_micat['um_per_px']
            except:
                pixel_um = 0.872 #From USAF resolution test
            
            break_limit = 190000
            results = {}
            i = 0

            for axs in ['x','y']:
                results[axs] = {}
                this_step_size = {
                    'x':0,
                    'y':0
                }
                for dir in [1, -1]:
                    i += 1
                    this_step_size[axs] = step_sizes[axs] * dir

                    autofocus.looping_autofocus(dz = 1000)

                    starting_pos = list(stage.position.values())
                    logger.info(f"Starting at {starting_pos}")

                    #First loop finds maximum displacement in positive x direction

                    delta = {
                        'x':10001,
                        'y':10001
                    }
                    tot_dis_xpos = 0
                    displacement_xpos = []
                    displacement_y = []
                    dis_mag_xpos = []
                    tot_mag_xpos = 0
                    steps_xpos = []
                    totMag_eachStep_xpos = [] #This variable tracks the total distance travelled after each movement
                    stage_coord_xpos = []
                    # TODO add retry failed move, just in case
                    while np.abs(delta[axs]) > minimum_offset[axs]:  #loop will continue until pixel distance is less than some value
                        pos = stage.position
                        if np.abs(pos[axs] - starting_pos[2]) >= break_limit:
                            logging.warning("Break limit met")
                            break
                        
                        image1 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)
                        image1=image1.tolist()

                        if len(stage_coord_xpos) > 1:
                            z_diff = stage_coord_xpos[-1][2] - stage_coord_xpos[-2][2]
                        else:
                            z_diff = 0
                        
                        # TODO combine these into one move
                            
                        # Move down first to avoid hitting sample
                        stage.move_relative(z = z_diff)
                        csm.move_in_image_coordinates(x = this_step_size['x'], y = this_step_size['y'])
                        

                        steps_xpos.append(stage.position[axs])
                        failure_count = 0
                        while failure_count < 4:
                            autofocus.looping_autofocus(dz = 1500)

                            image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)
                            
                            image2=image2.tolist()
                            offset = [x * 1 for x in csm.get_displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                            delta['x'] = int(offset[1])
                            delta['y'] = int(offset[0])
                            logger.info(f"Most recent move was {delta}. Threshold is {minimum_offset}")
                            if np.abs(delta[axs]) > minimum_offset[axs]:
                                failure_count = 10
                            else:
                                failure_count += 1
                                logger.info(f'Looks like that move failed. Going to retry. Attempt {failure_count} out of 4')

                        displacement_xpos.append(delta['x'] * pixel_um) #converts to um
                        displacement_y.append(delta['y'] * pixel_um) #converts to um 
                        tot_dis_xpos = tot_dis_xpos + (delta['y'] * pixel_um) #This just takes x-axis data not magnitude
                        dis_mag_xpos.append(np.sqrt((delta['y'])**2+(delta['x'])**2)) #magnitude of displacement
                        tot_mag_xpos = tot_mag_xpos + (np.sqrt((delta['y'])**2+(delta['x'])**2)*pixel_um) #converts to um
                        totMag_eachStep_xpos.append(tot_mag_xpos)
                        stage_coord_xpos.append(list(stage.position.values()))

                    
                    #TODO: make this move to the centre instead of the start
                    stage.move_absolute(x = starting_pos[0], y = starting_pos[1], z = starting_pos[2])
                    pos = starting_pos.copy()
                    logger.info(f"Loop {i} done")
                    
                    results[axs][dir] = {
                        "stage_lateral_steps" : steps_xpos,
                        "correlation_lateral_steps": totMag_eachStep_xpos,
                        "stage_positions": stage_coord_xpos
                    }
                    
                z_pos_list = [pos[2] for pos in stage_coord_xpos]
                max_index = np.argmax(z_pos_list)
                x_max_pos = stage_coord_xpos[max_index][0]
                logging.info(f'Apparent peak was at {x_max_pos}. We started at {starting_pos[0]}')

            results['csm'] = csm.image_to_stage_displacement_matrix
            
            self.thing_settings["rom_data"] = DenumpifyingDict(results).model_dump()
            return results
        
        except:
            logger.error("Stopping measurement because it was cancelled by the user")
            stage.move_absolute(x = starting_position[0], y = starting_position[1], z = starting_position[2], block_cancellation=True)
            raise Exception
            

    @thing_property
    def rom_data(self) -> Optional[Dict]:
        """The results of the last calibration that was run
        """
        return self.thing_settings.get("rom_data", None)
        

class RecentringThing(Thing):
    @thing_action
    def recentre(
        self,
        autofocus: AutofocusDep,
        stage: StageDep,
        logger: InvocationLogger,
        max_steps=15,
        lateral_distance=2500,
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
        starting_position = list(stage.position.values())
        try:
            dx = lateral_distance

            centre = list(stage.position.values())

            # A list of all the positions we've focused
            focused_pos = [[], []]

            logger.info(f"Recentring the stage. Starting at {centre}")

            autofocus.looping_autofocus()

            for direction in [0, 1]:
                # Start off with the current position, and moving in the positive direction

                logger.info(f"Moving along the {['x','y'][direction]} axis")
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
                    attempts = 0
                    while attempts < 5:
                        jpeg_zs, jpeg_sizes = autofocus.looping_autofocus(dz=1500, start = 'centre')
                        time.sleep(0.2)
                        autofocus_success = autofocus.verify_focus_sharpness(sweep_sizes = jpeg_sizes, wrappedcamera = CamDep, threshold = 0.85)
                        if autofocus_success:
                            break
                        else:
                            attempts += 1
                    position = list(stage.position.values())
                    focused_pos[direction].append(position)

                    steps += 1
                    if steps > max_steps:
                        logger.warning(
                            "Couldn't find a suitable position. Roughly centre the stage and check your sample is suitable for autofocus"
                        )
                        break
                    
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

                    if len(focused_pos[direction]) >= 3:
                        if (
                            np.argmax(sorted_all_heights) > 1
                            and np.argmax(sorted_all_heights) < len(all_heights) - 2
                        ):
                            logger.info(
                                f"Breaking because the highest point is at {np.argmax(sorted_all_heights)} in the list"
                            )
                            # plt.plot(sorted_lateral, sorted_all_heights,'.')
                            # plt.plot(sorted_lateral, quad_fit_func(sorted_lateral))
                            # plt.show()
                            break
                        else:
                            if turning_loc < np.mean(sorted_lateral):
                                moves = -1
                            elif turning_loc > np.mean(sorted_lateral):
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
                autofocus.looping_autofocus()
            
            logger.info(f"Centre of ROM is at {centre[:2], stage.position['z']}")

            logger.debug(f"List of positions is {focused_pos}")

            with open(r'logs/stage_recentre.json', 'w', encoding='utf-8') as f:
                json.dump(focused_pos, f, ensure_ascii=False, indent=4)

            logger.info("Setting the centre of the range of motion to 0, 0, 0")
            stage.set_zero_position()

            self.thing_settings["recentring_data"] = focused_pos
            return focused_pos

        except InvocationCancelledError:
            stage.move_absolute(x = starting_position[0], y = starting_position[1], z = starting_position[2], block_cancellation=True)
            logger.error("Stopping measurement because it was cancelled by the user")
            raise Exception


    @thing_property
    def recentring_data(self) -> Optional[Dict]:
        """The results of the last calibration that was run
        """
        return self.thing_settings.get("recentring_data", None)