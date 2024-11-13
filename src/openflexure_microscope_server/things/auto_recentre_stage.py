import numpy as np
import logging
import cv2
import json
from PIL import Image
import time
from typing import Annotated, Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple
from scipy.optimize import curve_fit

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

def function(x, a, b, c):   #TODO rename this function
    return a * x**2 + b * x + c

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
            start_time = time.time()

            lateral_offset = 60 #By what percentage of the image/stream resolution the stage moves
            stream_resolution = cam.stream_resolution

            step_sizes = {
                'x' : (lateral_offset / 100) * stream_resolution[0],
                'y' : (lateral_offset / 100) * stream_resolution[1],
            }

            

            minimum_offset = { #minimum we expect the stage to move each time?
                'x' : int(step_sizes['x'] * 0.8),
                'y' : int(step_sizes['y'] * 0.8),
            }

            this_step_size = {}

            try:
                pixel_um = micat.last_micat['um_per_px'] #Is this meant to try to run the MICAT software to extract the um/pixel?
            except:
                pixel_um = 0.872 #From USAF resolution test
            
            break_limit = 190000
            
            wrong_axis_max = {
                'x': step_sizes['y'] * 0.1,
                'y': step_sizes['x'] * 0.1
    
            }

            logger.info(f"Maximum allowed movement in wrong axis is x:{wrong_axis_max['x']} and y:{wrong_axis_max['y']}")
            #wrong_axis_max = 40
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
                    focused_positions = []
                    # TODO clean these up
                    totMag_eachStep_xpos = [] #This variable tracks the total distance travelled after each movement
                    stage_coords = []
                    failure_count = 0
                    wrong_axis_detect = False

                    while np.abs(delta[axs]) > minimum_offset[axs] and failure_count < 4:  #loop will continue until pixel distance is less than some value
                        pos = stage.position

                        if i == 1 or i == 2:
                            wrong_delta = 'y'
                            delta[wrong_delta] = 0
                        elif i==3 or i==4:
                            wrong_delta = 'x'
                            delta[wrong_delta] = 0

                        if np.abs(pos[axs] - starting_pos[2]) >= break_limit:
                            logging.warning("Break limit met")
                            break

                        if wrong_axis_detect == True:
                            break
                        
                        # Capture the base image
                        image1 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)
                        test_image1 = cam.grab_jpeg()
                        image1=image1.tolist()

                        # Plan the next move
                        # xy offset is regular, z is calculated
                        if len(focused_positions) >= 4:
                            lateral_positions = [i[axs] for i in focused_positions]
                            logger.info(f'Lateral locs are {lateral_positions}')
                            z_positions = [i['z'] for i in focused_positions]
                            logger.info(f'Lateral locs are {z_positions}')
                            parameters, covariance = curve_fit(function, lateral_positions, z_positions)
                            relative_move = stage_coords[1][axs] - stage_coords[0][axs]
                            z_dest = function(stage.position[axs] + relative_move, *parameters)
                            logger.info(f'z destination is {z_dest} for lateral position {stage.position[axs] + relative_move}')
                            z_diff = z_dest - stage.position['z']
                        elif len(stage_coords) > 1:
                            z_diff = stage_coords[-1]['z'] - stage_coords[-2]['z']
                        else:
                            z_diff = 0
                        
                        logger.info(f'path is {stage_coords}')
                        logger.info(f'current position is {stage.position}')
                        # TODO combine these into one move
                            
                        # Move down first to avoid hitting sample
                        stage.move_relative(z = z_diff)
                        logger.info('Moved in Z.')
                        csm.move_in_image_coordinates(x = this_step_size['x'], y = this_step_size['y'])
                        logger.info('Moved in X/Y.')
                        
                        #failure_count = 0
                        while failure_count < 4:
                            # if failure_count > 0 or len(focused_positions) < 4:
                            focused = 1
                            autofocus.looping_autofocus(dz = 800)
                            # else:
                            #     focused = 0
                            #     logger.info('skipping autofocus')

                            image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)
                            
                            image2=image2.tolist()
                            offset = [x * 1 for x in csm.get_displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                            delta['x'] = int(offset[1])
                            delta['y'] = int(offset[0])
                            logger.info(f"Most recent move was {delta}. Target is {this_step_size}. Threshold is {minimum_offset}")

                            #Check for extreme movement in the wrong axis
                            if np.abs(delta[wrong_delta]) > wrong_axis_max[wrong_delta]:
                                logger.info('Erroneous motion in the wrong axis detected. Edge found.')
                                wrong_axis_detect = True
                                test_image1.save(f"/var/openflexure/scans/loop{i}_image1_error_motion.jpeg")
                                test_image2 = cam.grab_jpeg()
                                test_image2.save(f"/var/openflexure/scans/loop{i}_image2_error_motion.jpeg")
                                break

                            if np.abs(delta[axs]) > minimum_offset[axs]:
                                if focused:
                                    focused_positions.append(stage.position)
                                break
                            else:
                                failure_count += 1
                                
                                test_image1.save(f"/var/openflexure/scans/loop{i}_image1_initial_fail.jpeg")
                                test_image2 = cam.grab_jpeg()
                                test_image2.save(f"/var/openflexure/scans/loop{i}_image2_initial_fail.jpeg")
                                logger.info(f'Image captured for analysis.') 
                                logger.info(f'Looks like that move failed. Going to retry. Attempt {failure_count} out of 4')


                        #Beginning of the second attempt to validate the move
                        if failure_count == 4:
                            
                            #Moves 300 steps beyond the previous position and back again to account for backlash
                            #Tidy this up
                            step_sizes_backlash = {

                                'x' : ((lateral_offset / 100) * stream_resolution[0]) + 300,
                                'y' : ((lateral_offset / 100) * stream_resolution[1]) + 300

                            }

                            this_step_size_backlash = {
                                'x':0,
                                'y':0
                            }

                            this_step_size_backlash[axs] = step_sizes_backlash[axs] * dir

                            return_move = {
                                'x':0,
                                'y':0
                            }

                            return_move[axs] = (return_move[axs] + 300) * dir

                            logger.info(f'Loop {i} edge may have been found. Moving back to previous position and checking in smaller step sizes.')
                            csm.move_in_image_coordinates(x = -this_step_size_backlash['x'], y = -this_step_size_backlash['y'])
                            csm.move_in_image_coordinates(x = return_move['x'], y = return_move['y'])
                            logger.info(f'current position is {stage.position}')
                            autofocus.looping_autofocus(dz = 800)
                            lateral_offset_check = 15 #By what percentage of the image/stream resolution the stage moves
                            step_sizes_check = {
                                'x' : (lateral_offset_check / 100) * stream_resolution[0],
                                'y' : (lateral_offset_check / 100) * stream_resolution[1],
                            }

                            this_step_size_check = {
                                'x':0,
                                'y':0
                            }

                            this_step_size_check[axs] = step_sizes_check[axs] * dir

                            delta_check = {
                                'x':10001,
                                'y':10001
                            }

                            minimum_offset_check = { #minimum we expect the stage to move each time?
                                'x' : int(step_sizes_check['x'] * 0.3),
                                'y' : int(step_sizes_check['y'] * 0.3),
                            }

                            retry_count = 0
                            index = 0

                            logger.info(f'Variables set.')

                            for loop in range(0,3): #At this point, it moves the stage in smaller increments.
                                #while np.abs(delta_check[axs]) > minimum_offset_check[axs]:  #loop will continue until pixel distance is less than some value
                                index = index + 1

                                if retry_count == 4:
                                    logger.info(f'Small movement cancelled.')
                                    break

                                logger.info(f'Small movement {loop + 1}/3')
                                pos = stage.position
                                if np.abs(pos[axs] - starting_pos[2]) >= break_limit:
                                    logging.warning("Break limit met")
                                    break
                                
                                # Capture the base image
                                image1 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)
                                image1=image1.tolist()
                                test_image1 = cam.grab_jpeg()
                                test_image1.save(f"/var/openflexure/scans/loop{i}_image1_retry.jpeg")
                                logger.info(f'Image 1 Captured')
                                
                                # TODO combine these into one move
                                
                                logger.info(f'current position is {stage.position}')
                                logger.info(f'Move pending for small movement {loop + 1}/3')
                                csm.move_in_image_coordinates(x = this_step_size_check['x'], y = this_step_size_check['y'])
                                
                                retry_count = 0
                                while retry_count < 4:
                                    focused = 1
                                    autofocus.looping_autofocus(dz = 800)

                                    image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)
                                    image2=image2.tolist()

                                    test_image2 = cam.grab_jpeg()
                                    test_image2.save(f"/var/openflexure/scans/loop{i}_image2_retry.jpeg")

                                    logger.info(f'Image 2 captured.')

                                    offset = [x * 1 for x in csm.get_displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                                    delta_check['x'] = int(offset[1])
                                    delta_check['y'] = int(offset[0])
                                    logger.info(f"Most recent move was {delta_check}. Target is {this_step_size_check}. Threshold is {minimum_offset_check}")
                                    if np.abs(delta_check[axs]) > minimum_offset_check[axs]:
                                        if focused:
                                            focused_positions.append(stage.position)
                                        break
                                    else:
                                        retry_count += 1
                                        logger.info(f'Looks like that move failed. Going to retry. Retry attempt {retry_count} out of 4')

                                if index == 3 and retry_count != 4:
                                    delta = {
                                        'x':10001,
                                        'y':10001
                                    }

                                    failure_count = 0

                        totMag_eachStep_xpos.append(offset)
                        stage_coords.append(stage.position)

                    
                    #TODO: make this move to the centre instead of the start
                    stage.move_absolute(x = starting_pos[0], y = starting_pos[1], z = starting_pos[2])
                    pos = starting_pos.copy()
                    logger.info(f"Loop {i} done")
                    
                    results[axs][dir] = {
                        "correlation_lateral_steps": totMag_eachStep_xpos,
                        "stage_positions": stage_coords
                    }
                    
                z_pos_list = [pos['z'] for pos in stage_coords]
                logger.info(f'Z positions are {z_pos_list}')
                max_index = np.argmax(z_pos_list)
                x_max_pos = stage_coords[max_index]['x']
                logging.info(f'Apparent peak was at {x_max_pos}. We started at {starting_pos[0]}')

            end_time = time.time()
            total_time = (end_time - start_time)/60 #converting to minutes
            logger.info(f"Range of motion measurement took {int(total_time)} minutes.")
            results['Time(minutes)'] = total_time

            results['csm'] = csm.image_to_stage_displacement_matrix
            
            self.thing_settings["rom_data"] = DenumpifyingDict(results).model_dump()
            return results
        
        except:
            logger.error("Stopping measurement because it was cancelled by the user")
            end_time = time.time()
            total_time = (end_time - start_time)/60 #converting to minutes
            logger.info(f"Cancelled range of motion measurement after {int(total_time)} minutes.")
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