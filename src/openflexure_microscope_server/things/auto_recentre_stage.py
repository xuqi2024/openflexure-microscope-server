import numpy as np
import logging
import cv2
import json
from PIL import Image
import time
from typing import Annotated, Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple
from scipy.optimize import curve_fit
from camera_stage_mapping import camera_stage_tracker
from camera_stage_mapping import fft_image_tracking

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.dependencies.invocation import CancelHook, InvocationLogger, InvocationCancelledError
from labthings_fastapi.decorators import thing_action, thing_property
from .stage import StageDependency as StageDep
from labthings_sangaboard import SangaboardThing
from labthings_picamera2.thing import StreamingPiCamera2
from labthings_fastapi.types.numpy import NDArray, denumpify, DenumpifyingDict
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper
#from openflexure_microscope_server.things.camera_stage_mapping import camera_stage_tracker

StageDep = direct_thing_client_dependency(SangaboardThing, "/stage/")
CamDep = direct_thing_client_dependency(StreamingPiCamera2, "/camera/")
CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")

def quadratic(x, a, b, c):  
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
        starting_position = list(stage.position.values()) #This is done later as well, this might need removed.

        try:
            
            #for repeat_test in range(20):
            logger.info("Using the stage to measure the range of motion")
            #starting_pos_image = cam.grab_jpeg()
            start_time = time.time()
            filepath = "/var/openflexure/"
            #starting_pos_image.save(f"{filepath}cycle{repeat_test}_starting_pos.jpeg")
            stream_resolution = cam.stream_resolution
            
            #Define the percentages of the FOV that the stage will move by
            big_step = 200
            small_step = 20

            step_sizes_big = {
                'x':(big_step/100) * stream_resolution[0],
                'y':(big_step/100) * stream_resolution[1]
            }

            step_sizes_small = {
                'x':(small_step/100) * stream_resolution[0],
                'y':(small_step/100) * stream_resolution[1]
            }

            minimum_offset_small = {
                'x' : (small_step/100) * stream_resolution[0] * 0.8,
                'y' : (small_step/100) * stream_resolution[1] * 0.8
            }

            z_perc = 50

            z_steps = {
                'x':(z_perc/100) * stream_resolution[0],
                'y':(z_perc/100) * stream_resolution[1]
            }

            minimum_offset_z = {
                'x' : (z_perc/100) * stream_resolution[0] * 0.8,
                'y' : (z_perc/100) * stream_resolution[1] * 0.8
            }

            this_big_step_size = {}
            this_small_step_size = {}
            z_cal_step = {}
            
            break_limit = 190000

            #logger.info(f"Maximum allowed movement in wrong axis is x:{wrong_axis_max['x']} and y:{wrong_axis_max['y']}")
            #wrong_axis_max = 40
            results = {}
            i = 0

            for axs in ['x','y']:
                results[axs] = {}
                this_big_step_size = {
                    'x':0,
                    'y':0
                }

                this_small_step_size = {
                    'x':0,
                    'y':0
                }

                z_cal_step = {
                    'x':0,
                    'y':0
                }
                for dir in [1, -1]:
                    i += 1
                    this_big_step_size[axs] = step_sizes_big[axs] * dir
                    this_small_step_size[axs] = step_sizes_small[axs] * dir
                    z_cal_step[axs] = z_steps[axs] * dir 

                    autofocus.looping_autofocus(dz = 1000)

                    starting_pos = list(stage.position.values())
                    logger.info(f"Starting at {starting_pos}")

                    #First loop finds maximum displacement in positive x direction

                    delta = {
                        'x':10001,
                        'y':10001
                    }

                    z_delta = {}

                    focused_positions = []
                    # TODO clean these up
                    cor_lat_steps = [] #This variable tracks the total distance travelled after each movement
                    stage_coords = []
                    #axis_fail = False

                    #Set of moves to gather information for the curve_fit
                    #The step size here should be around 50% of the FOV

                    z_coord = []
                    z_coord.append(stage.position)
                    
                    csm.move_in_image_coordinates(x = this_big_step_size['x'], y = this_big_step_size['y'])
                    autofocus.looping_autofocus(dz = 800)
                    z_coord.append(stage.position)
                    stage.move_absolute(x = starting_pos[0], y = starting_pos[1], z = starting_pos[2])
                    autofocus.looping_autofocus(dz = 800)

                    logger.info(f"Medium sized steps to find Z calibration for loop {i}")

                    for loop in range(4):
                        stage_coords.append(stage.position)
                        logger.info(f"Current position is {stage.position}")
                        image1 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                        image1=image1.tolist()
                        csm.move_in_image_coordinates(x = z_cal_step['x'], y = z_cal_step['y'])
                        autofocus.looping_autofocus(dz = 800)
                        image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                        image2=image2.tolist()
                        offset = [x * 1 for x in fft_image_tracking.displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                        delta['x'] = int(offset[1])
                        delta['y'] = int(offset[0])
                        logger.info(f"Displacement found was {np.abs(delta[axs])}. Minimum offset is {minimum_offset_z[axs]}")
                        focused_positions.append(stage.position)  #focused_positions is used for z calibration
                        #if np.abs(delta[axs]) < minimum_offset_z[axs]:  #this means the edge has been found
                            #logger.info(f"Something is wrong with the correlation.")
                            #axis_fail = True
                            #break
                            
                    #if axis_fail == True:
                        #break
                    
                    z_delta['x'] = int(offset[1])
                    z_delta['y'] = int(offset[0])

                    lateral_positions = [i[axs] for i in focused_positions]
                    logger.info(f"Lateral positions for loop {i} are {lateral_positions}")
                    z_positions = [i['z'] for i in focused_positions]
                    logger.info(f"z_positions for loop {i} are {z_positions}")
                    parameters, covariance = curve_fit(quadratic, lateral_positions, z_positions)
                    logger.info(f"Parameters for loop {i} are {parameters}")

                    logger.info(f"Z calibration complete.")

                    while np.abs(delta[axs]) > minimum_offset_small[axs] and np.abs(z_delta[axs]) > minimum_offset_z[axs]:  #loop will continue until pixel distance is less than some value
                        pos = stage.position

                        if np.abs(pos[axs] - starting_pos[2]) >= break_limit:
                            logging.warning("Break limit met")
                            break

                        #Predicts best z move based on first 4 moves to avoid hitting sample
                        
                        logger.info(f"Coordinates for prediction are {z_coord[0]} and {z_coord[1]}")
                        relative_move = z_coord[1][axs] - z_coord[0][axs]
                        z_dest = quadratic(stage.position[axs] + relative_move, *parameters)
                        z_diff = z_dest - stage.position['z']

                        stage.move_relative(z = z_diff)

                        logger.info(f"Moved in z by {z_diff}") 

                        #Big movement
                        logger.info(f"Current position is {stage.position}")
                        logger.info(f"Large sized step for loop {i}")
                        stage_coords.append(stage.position)
                        csm.move_in_image_coordinates(x = this_big_step_size['x'], y = this_big_step_size['y'])
                        autofocus.looping_autofocus(dz = 1000)
                        logger.info(f"Current position is {stage.position}")

                        lateral_positions = [i[axs] for i in focused_positions]
                        z_positions = [i['z'] for i in focused_positions]
                        parameters, covariance = curve_fit(quadratic, lateral_positions, z_positions)
                        logger.info("Recalculated Z calibration.")

                        #3 small movements, each of which is correlated
                        logger.info(f"3 small sized steps for loop {i}")
                        failure_count = 0
                        for loop in range(3):
                            stage_coords.append(stage.position)
                            focused_positions.append(stage.position)
                            image1 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                            image1=image1.tolist()
                            test_image1 = cam.grab_jpeg()
                            csm.move_in_image_coordinates(x = this_small_step_size['x'], y = this_small_step_size['y'])
                            autofocus.looping_autofocus(dz = 400)
                            image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                            image2=image2.tolist()
                            test_image2 = cam.grab_jpeg()
                            offset = [x * 1 for x in fft_image_tracking.displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                            delta['x'] = int(offset[1])
                            delta['y'] = int(offset[0])
                            logger.info(f"Displacement found was {np.abs(delta[axs])}. Minimum offset is {minimum_offset_small[axs]}")
                            logger.info(f"Current position is {stage.position}")
                            cor_lat_steps.append(offset)

                            #Refocuses and tests new image to check that the focus wasn't just off
                            while np.abs(delta[axs]) < minimum_offset_small[axs] and failure_count < 3:
                                logger.info(f"Correlation failed. Refocusing to check. Attempt {failure_count + 1}/3")
                                autofocus.looping_autofocus(dz = 1000)
                                image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                                image2=image2.tolist()
                                failure_count = failure_count + 1
                                offset = [x * 1 for x in fft_image_tracking.displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                                delta['x'] = int(offset[1])
                                delta['y'] = int(offset[0])
                                logger.info(f"Displacement found was {np.abs(delta[axs])}. Minimum offset is {minimum_offset_small[axs]}")
                                cor_lat_steps.append(offset)


                            if np.abs(delta[axs]) < minimum_offset_small[axs] and failure_count == 3:  #this means the edge has been found
                                logger.info(f"Edge of loop {i} has been found.")
                                test_image1.save(f"{filepath}loop{i}_image1.jpeg")
                                test_image2.save(f"{filepath}loop{i}_image2.jpeg")
                                break
                    
                        stage_coords.append(stage.position)
                        focused_positions.append(stage.position)

                    #Now we move the stage until we detect movement and take that position as final. This is to account for the extra motion carried out by the big step.

                    logger.info(f"Running motion detection for loop {i}")

                    displacements = np.array([1,2,4,8,16,32,64,128,256,512,1024])  #Array of increasing step sizes
                    motion_minimum = 20  #minimum nuber of pixels for motion to be detected

                    this_motion_step = {
                        'x':np.zeros(8),
                        'y':np.zeros(8),
                        'z':0
                    }

                    this_motion_step[axs] = displacements * dir
                    
                    for loop in range(8):
                        logger.info(f"Testing with step size {this_motion_step[axs][loop]}")
                        image1 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                        image1=image1.tolist()
                        stage.move_relative(x = this_motion_step['x'][loop], y = this_motion_step['y'][loop], z = this_motion_step['z'])
                        image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                        image2=image2.tolist()
                        offset = [x * 1 for x in fft_image_tracking.displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                        delta['x'] = int(offset[1])
                        delta['y'] = int(offset[0])
                        logger.info(f"Offset measured as {delta[axs]}")
                        if np.abs(delta[axs]) > motion_minimum:
                            logger.info("Motion detected.")
                            break

                    stage_coords.append(stage.position)

                    final_pos = stage.position
                    
                    #TODO: make this move to the centre instead of the start
                    stage.move_absolute(x = starting_pos[0], y = starting_pos[1], z = starting_pos[2])
                    pos = starting_pos.copy()
                    logger.info(f"Loop {i} done")
                    
                    results[axs][dir] = {
                        "correlation_lateral_steps": cor_lat_steps,
                        "stage_positions": stage_coords,
                        "final_position": final_pos
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

            results['csm'] = csm.image_to_stage_displacement_matrix #This doesn't change on each run, it is data intrinsic to the microscope
            
            self.thing_settings["rom_data"] = DenumpifyingDict(results).model_dump()

            with open("/var/openflexure/ROM_Test_Results.json", 'w') as file_object:
                json.dump(results, file_object, indent = 3)

                # import os

                # file_i = 0 
                # while os.path.isfile(f'logs/stage_{file_i}.json'):
                #     file_i += 1

                # with open(f'logs/stage_{file_i}.json', 'w', encoding='utf-8') as f:
                #     json.dump(results, f, ensure_ascii=False, indent=4)

            return results

                
                #file_i += 1
        
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
        logging: InvocationLogger,
        max_steps=15,
        lateral_distance=2000
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

        autofocus.looping_autofocus()

        logging.info(f"The intervals between steps is {dx}.")
        logging.info(f"Starting position is {centre}")

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
                autofocus.looping_autofocus()
                position = list(stage.position.values())
                logging.info(f"Current position is {position}")
                focused_pos[direction].append(position)

                logging.info(focused_pos[direction])

                steps += 1
                if steps > max_steps:
                    logging.warning(
                        "Couldn't find a suitable position. Roughly centre the stage and check your sample is suitable for autofocus"
                    )
                    break

                if len(focused_pos[direction]) > 4:
                    logging.info("Calculating turning point.")
                    all_heights = [x[2] for x in focused_pos[direction]] #Extracting all focused z positions
                    direction_index = [x[direction] for x in focused_pos[direction]] #Extracting all x/y positions depending on direction of travel

                    sorted_all_heights = [
                        x for y, x in sorted(zip(direction_index, all_heights))
                    ]

                    sorted_lateral = sorted(direction_index)
                    quad_fit = np.polyfit(sorted_lateral, sorted_all_heights, 2)
                    quad_fit_func = np.poly1d(quad_fit) #Turns polynomial into convenient class that makes it easier to operate on

                    turning = quad_fit_func.deriv() #Differentiates the function and returns the coefficients of each term in the polynomial

                    logging.info(f"Output of deriv function is {turning}")

                    turning_loc = -turning[0] / (turning[1]) #The [0] refers to the first coefficient ie A in Ax + C where C is a constant term

                    logging.warning(sorted_all_heights)
                    if (                                       #Breaks the loop if the index of the maximum is anywhere but the start of the array
                        np.argmax(sorted_all_heights) != 0
                        and np.argmax(sorted_all_heights) != len(all_heights) - 1
                    ):
                        logging.info(
                            f"Breaking because the highest point is at {np.argmax(sorted_all_heights)} in the list"
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
                    break

            # Centre value is replaced by the maximum value recorded in that axis
            #centre[direction] = focused_pos[direction][np.argmax(all_heights)][
            #    direction
            #]
            centre[direction] = turning_loc
            logging.info(f"Moving to new center position {centre}")
            stage.move_absolute(x=centre[0], y=centre[1], z=centre[2])
            autofocus.looping_autofocus()

        logging.info(f"Centre of ROM is at {centre, stage.position['z']} \n")

        results = {
            "Calculated Centre": centre,
            "Positions": sorted_all_heights,
            "Interval": dx
        }

        with open("/var/openflexure/recentre_results.json", 'w') as file_object:
            json.dump(results, file_object, indent = 3)

        return focused_pos
