import numpy as np
import logging
import os
import cv2
import json
from PIL import Image
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
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

StageDep = direct_thing_client_dependency(SangaboardThing, "/stage/")
CamDep = direct_thing_client_dependency(StreamingPiCamera2, "/camera/")
CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")

def quadratic(x, a, b, c):  
    return a * x**2 + b * x + c

def straight_line(x,m,c):
    return m*x + c

#This function is used in the range of motion analysis.
def pattern_gen(max_index, first_index):
    '''
    Generates a list of integers with the required pattern for the stage postitions we are interested in analysing.
    Input - Max_index: the maximum integer in the array, typically the shape of the data set.
    first_index - whether the list starts from 0 or 1.
    '''
    max_index = max_index - 1
    index = np.arange(first_index, first_index + 4, 1)
    index = np.ndarray.tolist(index)
    index_reached = False
    while np.max(index) < max_index:
        index.append(np.max(index) + 2)
        if np.max(index) >= max_index:
            if np.max(index) > max_index:
                index = index[:len(index)-1]
            break
        for loop in range(2):
            index.append(np.max(index) + 1)
            if np.max(index) >= max_index:
                index_reached = True
                break
        
        if index_reached == True:
            break

    return index

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

            stream_resolution = cam.stream_resolution

            res_dic = { #Separates resolution values into a dictionary
                'x':stream_resolution[0],
                'y':stream_resolution[1]
            }
        

            #Used a function to do this to make sure the syntax of all the required dictionaries is correct
            def dict_generate(small_step, z_perc, big_step):
                '''
                Generates the dictionaries required to run the rest of the code with correct naming convention using percentage field of view values.
            
                Input: 
                    small_step: Percentage of the field of view the stage moves for the smallest movements it will do.
                    z_perc: Percentage of the field of view the stage moves for the medium movements it will do.
                    big_step: Percentage of the field of view the stage moves for the largest movements it will do.

                Returns:
                    Dictionaries for the step size based on %FOV and the minimum offsets for small, medium and large step sizes.
                '''
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

                z_steps = {
                    'x':(z_perc/100) * stream_resolution[0],
                    'y':(z_perc/100) * stream_resolution[1]
                }

                minimum_offset_z = {
                    'x' : (z_perc/100) * stream_resolution[0] * 0.8,
                    'y' : (z_perc/100) * stream_resolution[1] * 0.8
                }
                return step_sizes_small, minimum_offset_small, z_steps, minimum_offset_z, step_sizes_big

            def motion(step_size, focus_range, minimum_offset, autofocus_proc, focus_data):
                '''
                Captures image, moves specified number of steps, captures a second image and correlates the two images. 
                This is the standard series of events all the way out to the edge.
            
                Input: 
                    step size(dict): Number of steps taken between correlations. Usually given in terms of % FOV. Should be names ['x'] and ['y']. Generated by dict_generate funtion.
                    focus_range(int): The number of steps scanned over to autofocus.
                    minimum_offset(dict): Minimum number of pixels required for a successful movement
                    autofocus_proc(boolean): If true, function will autofocus after each movement, otherwise will skip the autofocus procedure.
                    focus_data(array): Most recent autofocus data. Pass in entire array with no index.

                Returns:
                    offset: The pixel distance between two positions [y, x].
                    delta: Similar to offset but separated into a dictionary with labels 'x' and 'y'
                    image1: First image taken for comparison. Needs returned so that it can be used when refocusing
                    focus_data(array): Updated autofocus data
                '''
                image1 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                csm.move_in_image_coordinates(x = step_size['x'], y = step_size['y'])
                if autofocus_proc == True:
                    focus_data = autofocus.looping_autofocus(dz = focus_range)
                if np.max(focus_data[1]) < base_sharp and autofocus_proc == True:  #Autofocuses only when the previous sharpness value wasn't good enough
                    logger.info(f"Max sharpness is {np.max(focus_data[1])} which is less than the base sharpness {base_sharp}. Refocusing before continuing.")
                    focus_data = autofocus.looping_autofocus(dz = focus_range)
                image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                offset = [x * 1 for x in fft_image_tracking.displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                delta['x'] = int(offset[1])
                delta['y'] = int(offset[0])
                logger.info(f"Displacement found was {np.abs(delta[axs])}. Minimum offset is {minimum_offset[axs]}")

                return offset, delta, image1, focus_data

            logger.info("Using the stage to measure the range of motion. This will provide the number of steps across each axis.")
            start_time = time.time() #starts the timer
            filepath = "/var/openflexure/" #Location where any images or JSON files are saved

            m = autofocus.looping_autofocus(dz = 1000)

            base_sharp = np.max(m[1]) - 5000 
            
            #Generates all the required dictionaries for all the different step sizes it will need to complete the ROM test
            step_sizes_small, minimum_offset_small, z_steps, minimum_offset_z, step_sizes_big = dict_generate(20, 50, 200)

            #Opens the CSM settings json so that the pixel per step value can be read and saved
            with open('/var/openflexure/settings/camera_stage_mapping/settings.json') as f:
                csm_settings = json.load(f)

            #Should extract x and y separately because this assumes x and y are the same but for now it just averages between the two.
            pixel_per_step = ((1/abs(csm.image_to_stage_displacement_matrix[0][1])) + (1/abs(csm.image_to_stage_displacement_matrix[1][0])))/4

            this_big_step_size = {}
            this_small_step_size = {}
            z_cal_step = {}
            
            break_limit = 190000


            #Defines the maximum distance the stage can move in the wrong axis for medium and small movements
            wrong_axis_max_z = {
                'x':z_steps['x'] * 0.1,
                'y':z_steps['y'] * 0.1
            }

            wrong_axis_max_small = {
                'x':step_sizes_small['x'] * 0.1,
                'y':step_sizes_small['y'] * 0.1
            }
            
            #initialise final results dictionary to be dumped into a JSON file at the very end.
            results = {}
            i = 0

            for axs in ['x','y']:
                results[axs] = {}
                #Initialise the dictionaries used to define the steps and direction the stage will move in each iteration of the loop
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
                    #Defines the size and direction for this iteration of the loop
                    this_big_step_size[axs] = step_sizes_big[axs] * dir
                    this_small_step_size[axs] = step_sizes_small[axs] * dir
                    z_cal_step[axs] = z_steps[axs] * dir 

                    m = autofocus.looping_autofocus(dz = 1000)
                    #The lowest sharpness value allowed. If below this, autofocus procedure occurs. This is the maximum sharpness value of the first autofocus that occurs.

                    #m saves all the data from the autofocus and m[1] is the array of all the file sizes so the maximum one is the most in focus image.
                    #This base_sharp is used to check whether the images later are in focus

                    #initialising and saying that there is no problem with parasitic motion yet
                    axis_error = False

                    starting_pos = list(stage.position.values())
                    logger.info(f"Starting at {starting_pos}")

                    #First loop finds maximum displacement in positive x direction

                    delta = {       #initialised before any motion
                        'x':10001,
                        'y':10001
                    }

                    #Defines which axis is the wrong one ie which one should there be almost zero motion in.
                    if axs == 'x':
                        wrong_axis = 'y'
                        delta[wrong_axis] = 0
                    else:
                        wrong_axis = 'x'
                        delta[wrong_axis] = 0

                    z_delta = {}    #saves pixel separating of final medium step so that the program can't continue if this value is too low

                    focused_positions = [] #focused_positions is used for z calibration
                    cor_lat_steps = [] #This variable tracks the total distance travelled after each movement
                    stage_coords = [] #Saves all stage positions

                    #Set of moves to gather information for the curve_fit
                    #The step size here should be around 50% of the FOV

                    logger.info(f"Medium sized steps to find Z calibration for loop {i}")

                    stage_coords.append(stage.position)

                    for loop in range(4):
                        logger.info(f"Current position is {stage.position}")
                        offset, delta, image1, m = motion(step_size = z_cal_step, focus_range = 800, minimum_offset = minimum_offset_z, autofocus_proc = True, focus_data = m)
                        focused_positions.append(stage.position)  
                        cor_lat_steps.append(offset)
                        stage_coords.append(stage.position)
                        if np.abs(delta[wrong_axis]) > wrong_axis_max_z[wrong_axis]:
                            logger.info(f"Parasitic motion in the wrong axis detected. Displacement in {wrong_axis} was found as {delta[wrong_axis]}.")
                            axis_error = True
                            break 
                    
                    z_delta['x'] = int(offset[1])
                    z_delta['y'] = int(offset[0])

                    if axis_error == False:
                        
                        #Extracts all data so that it can be used for a curve fit.
                        lateral_positions = [i[axs] for i in focused_positions]
                        z_positions = [i['z'] for i in focused_positions]
                        parameters, covariance = curve_fit(quadratic, lateral_positions, z_positions)

                        logger.info(f"Z calibration complete.")

                    while np.abs(delta[axs]) > minimum_offset_small[axs] and np.abs(z_delta[axs]) > minimum_offset_z[axs] and axis_error == False:  #loop will continue until pixel distance is less than some value
                        pos = stage.position

                        if np.abs(pos[axs] - starting_pos[2]) >= break_limit:
                            logging.warning("Break limit met")
                            break

                        #Predicts best z move based on first 4 moves to avoid hitting sample
                        #Each movement should improve the fit
                        
                        relative_move = dir * 2 * res_dic[axs]/(2*pixel_per_step) #This is the number of steps to cover 200% of the FOV.
                        z_dest = quadratic(stage.position[axs] + relative_move, *parameters)
                        z_diff = z_dest - stage.position['z']

                        stage.move_relative(z = -z_diff)

                        logger.info(f"Moved in z by {-z_diff}") 

                        #Big movement
                        logger.info(f"Current position is {stage.position}")
                        logger.info(f"Large sized step for loop {i}")
                        csm.move_in_image_coordinates(x = this_big_step_size['x'], y = this_big_step_size['y'])
                        m = autofocus.looping_autofocus(dz = 1000)
                        logger.info(f"Current position is {stage.position}")
                        stage_coords.append(stage.position)

                        lateral_positions = [i[axs] for i in focused_positions]
                        z_positions = [i['z'] for i in focused_positions]
                        parameters, covariance = curve_fit(quadratic, lateral_positions, z_positions)
                        logger.info("Recalculated Z calibration.")

                        #3 small movements, each of which is correlated
                        logger.info(f"3 small sized steps for loop {i}")
                        failure_count = 0
                        for loop in range(3):
                            focused_positions.append(stage.position)
                            offset, delta, image1, m = motion(this_small_step_size, 400, minimum_offset_small, autofocus_proc = False, focus_data = m)
                            cor_lat_steps.append(offset)
                            
                            #Cancels the axis if there is too much motion in the wrong axis
                            if np.abs(delta[wrong_axis]) > wrong_axis_max_small[wrong_axis]:
                                logger.info(f"Parasitic motion in the wrong axis detected. Displacement in {wrong_axis} was found as {delta[wrong_axis]}.")
                                axis_error = True
                                stage_coords.append(stage.position)
                                break 

                            #Refocuses and tests new image to check that the focus wasn't just off
                            while np.abs(delta[axs]) < minimum_offset_small[axs] and failure_count < 3:
                                logger.info(f"Correlation failed. Refocusing to check. Attempt {failure_count + 1}/3")
                                m = autofocus.looping_autofocus(dz = 1000)
                                image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                                failure_count = failure_count + 1
                                offset = [x * 1 for x in fft_image_tracking.displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                                delta['x'] = int(offset[1])
                                delta['y'] = int(offset[0])
                                logger.info(f"Displacement found was {np.abs(delta[axs])}. Minimum offset is {minimum_offset_small[axs]}")

                            stage_coords.append(stage.position)

                            if np.abs(delta[axs]) < minimum_offset_small[axs] and failure_count == 3:  #this means the edge has been found
                                logger.info(f"Edge of loop {i} has been found.")
                                break
                    
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
                        stage.move_relative(x = this_motion_step['x'][loop], y = this_motion_step['y'][loop], z = this_motion_step['z'])
                        image2 = cv2.resize(np.array(Image.open(cam.grab_jpeg().open())), dsize=(0,0), fx= 1, fy= 1)           
                        offset = [x * 1 for x in fft_image_tracking.displacement_between_images(image_0 = image1, image_1 = image2, sigma=10, fractional_threshold=0.1, pad=True)] #Units is pixels
                        delta['x'] = int(offset[1])
                        delta['y'] = int(offset[0])
                        logger.info(f"Offset measured as {np.abs(delta[axs])}")
                        if np.abs(delta[axs]) > motion_minimum:
                            logger.info("Motion detected.")
                            break

                    stage_coords[np.shape(stage_coords)[0] - 1] = stage.position

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

            x_pos = results['x'][1]['final_position']['x']
            x_neg = results['x'][-1]['final_position']['x']
            y_pos = results['y'][1]['final_position']['y']
            y_neg = results['y'][-1]['final_position']['y']

            #rom stores the range of motion in steps (x, y).
            rom = [abs(x_pos - x_neg), abs(y_pos - y_neg)]
            end_time = time.time()
            total_time = (end_time - start_time)/60 #converting to minutes
            logger.info(f"Range of motion measurement took {int(total_time)} minutes.")
            logger.info(f"Measured range of motion is {rom[0]} X {rom[1]} steps.")
            results['Time(minutes)'] = total_time

            results['csm'] = csm.image_to_stage_displacement_matrix #This doesn't change on each run, it is data intrinsic to the microscope
            
            self.thing_settings["rom_data"] = DenumpifyingDict(results).model_dump()

            results['pixels/step'] = pixel_per_step

            with open("/var/openflexure/ROM_Test_Results.json", 'w') as file_object:
                json.dump(results, file_object, indent = 3)

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

    def rom_analysis(self):
        filename = "/var/openflexure/ROM_Test_Results.json"

        with open(filename, 'r') as file:
            data = json.load(file)
        
        csm_con = data['pixels/step'] * 2 #Number of pixels per step calculated by camera stage mapping calibration

        x_pos_final = data['x']['1']['final_position']['x']
        x_neg_final = data['x']['-1']['final_position']['x']
        y_pos_final = data['y']['1']['final_position']['y']
        y_neg_final = data['y']['-1']['final_position']['y']

        #Estimated centre
        x_middle = (x_pos_final + x_neg_final)/2
        y_middle = (y_pos_final + y_neg_final)/2
        center = [x_middle, y_middle]

        #Polarity of z-motor
        z_pos = []
        x_pos = []

        for dir in ['1', '-1']:
            for loop in range(np.shape(data['x'][dir]['stage_positions'])[0]):
                z_pos.append(data['x'][dir]['stage_positions'][loop]['z'])
                x_pos.append(data['x'][dir]['stage_positions'][loop]['x'])

        params, extra = curve_fit(parabola, x_pos, z_pos)

        polarity_value = 2 * params[0] #This is the coeficient of the x^2 term in the quadratic

        if polarity_value > 0:
            curvature = 'positive'
        elif polarity_value < 0:
            curvature = 'negative'
        elif polarity_value == 0:
            curvature = 'ERROR'

        #Range of Motion
        rom_x = round(((x_pos_final - x_neg_final) * pixel_um * csm_con /1000), 2)
        rom_y = round(((y_pos_final - y_neg_final) * pixel_um * csm_con /1000), 2)

        rom_x_steps = x_pos_final - x_neg_final
        rom_y_steps = y_pos_final - y_neg_final

        #camera Stage Mapping
        dif_dic = {} #stores the difference between consecutive x and y points
        stage_dic = {} #This is a subset of dif_dic but only contains the differences where we also have a correlation
        pos_dic = {} #stores all the x and y positions with correlations
        cor_dic = {} #stores all correlations and separates x and y

        #Loop finds the difference between consecutive x and y coordinates
        for axs in ['x','y']:
            dif_dic[axs] = {}
            for dir in ['1', '-1']:
                dif_array = [data[axs][dir]['stage_positions'][i + 1][axs] - data[axs][dir]['stage_positions'][i][axs] for i in range(len(data[axs][dir]['stage_positions']) - 1)]
                dif_dic[axs][dir] = dif_array

        #This loop extracts every difference in dif_dic where we have a correlation associated with it and saves it in stage_dic.
        for axs in ['x', 'y']:
            stage_dic[axs] = {}
            for dir in ['1', '-1']:
                temp_array = []
                max_index = np.shape(dif_dic[axs][dir])[0]
                cor_index = pattern_gen(max_index, 0)
                for i in cor_index:
                    temp_array.append(dif_dic[axs][dir][i])
                stage_dic[axs][dir] = temp_array
        
        x_full_stage_dic_fit = np.concatenate((np.array(stage_dic['x']['1'][:-1]), np.array(stage_dic['x']['-1'][:-1])))
        y_full_stage_dic_fit = np.concatenate((np.array(stage_dic['y']['1'][:-1]), np.array(stage_dic['y']['-1'][:-1])))
        x_full_stage_dic = np.concatenate((np.array(stage_dic['x']['1']), np.array(stage_dic['x']['-1'])))
        y_full_stage_dic = np.concatenate((np.array(stage_dic['y']['1']), np.array(stage_dic['y']['-1'])))

        #This extracts all the positions where we have a correlation and stores them in pos_dic.
        for axs in ['x', 'y']:
            pos_dic[axs] = {}
            for dir in ['1', '-1']:
                temp_array = []
                max_index = np.shape(data[axs][dir]['stage_positions'])[0]
                cor_index = pattern_gen(max_index, 1)
                for i in cor_index:
                    temp_array.append(data[axs][dir]['stage_positions'][i][axs])
                pos_dic[axs][dir] = temp_array

        x_stage_coord_fit = np.concatenate((np.array(pos_dic['x']['-1'][:-1]),np.array(pos_dic['x']['1'][:-1])))
        y_stage_coord_fit = np.concatenate((np.array(pos_dic['y']['-1'][:-1]),np.array(pos_dic['y']['1'][:-1])))
        x_stage_coord = np.concatenate((np.array(pos_dic['x']['1']),np.array(pos_dic['x']['-1'])))
        y_stage_coord = np.concatenate((np.array(pos_dic['y']['1']),np.array(pos_dic['y']['-1'])))

        #This loop separates the x and y value of all correlations.

        for axs in ['x', 'y']:
            cor_dic[axs] = {}
            for dir in ['1', '-1']:
                temp_array = []
                if axs == 'x':
                    axis = 1
                elif axs == 'y':
                    axis = 0
                for i in data[axs][dir]['correlation_lateral_steps']:
                    temp_array.append(i[axis])
                cor_dic[axs][dir] = temp_array

        x_full_cor_dic_fit = np.concatenate((np.array(cor_dic['x']['1'][:-1]), np.array(cor_dic['x']['-1'][:-1])))
        y_full_cor_dic_fit = np.concatenate((np.array(cor_dic['y']['1'][:-1]), np.array(cor_dic['y']['-1'][:-1])))
        x_full_cor_dic = np.concatenate((np.array(cor_dic['x']['1']), np.array(cor_dic['x']['-1'])))
        y_full_cor_dic = np.concatenate((np.array(cor_dic['y']['1']), np.array(cor_dic['y']['-1'])))

        #For each loop, we have a version of the array without the last points of each axis that we use for fitting. This is because the last point is always going to fail and
        #will affect the fit. We keep a version of the array with every point for plotting.

        #Calculating the number of pixels per step in x and y at every point we can. Again, we have one for fitting and one for plotting.
        x_full_pixel_step_fit = x_full_cor_dic_fit/x_full_stage_dic_fit
        y_full_pixel_step_fit = y_full_cor_dic_fit/y_full_stage_dic_fit

        x_full_pixel_step = x_full_cor_dic/x_full_stage_dic
        y_full_pixel_step = y_full_cor_dic/y_full_stage_dic

        #Best fit for x_axis

        params_csm_x, extra_csm_x = curve_fit(straight_line, x_stage_coord_fit, np.abs(x_full_pixel_step_fit))

        xaxis_coord = np.arange(np.min(x_stage_coord_fit), np.max(x_stage_coord_fit), 1)
        xaxis_pixel_step = straight_line(xaxis_coord, params_csm_x[0], params_csm_x[1])

        #Best fit for y_axis

        params_csm_y, extra_csm_y = curve_fit(straight_line, y_stage_coord_fit, np.abs(y_full_pixel_step_fit))

        yaxis_coord = np.arange(np.min(y_stage_coord_fit), np.max(y_stage_coord_fit), 1)
        yaxis_pixel_step = straight_line(yaxis_coord, params_csm_y[0], params_csm_y[1])

        #Error Analysis
        #For ROM, take standard deviation of all correlations in x and all correlations in y separately exluding the first 4 correlations

        x_cor_small_movements = np.concatenate((np.array(cor_dic['x']['1'][4:]), np.array(cor_dic['x']['-1'][4:]))) #all small correlations in x
        y_cor_small_movements = np.concatenate((np.array(cor_dic['y']['1'][4:]), np.array(cor_dic['y']['-1'][4:]))) #all small correlations in y

        rom_err_x = np.std(x_cor_small_movements) #in pixel units
        rom_err_y = np.std(y_cor_small_movements) #in pixel units

        rom_err_x_mm = rom_err_x * pixel_um/1000
        rom_err_y_mm = rom_err_y * pixel_um/1000

        #Check for and create if necessary, a folder called Graphs where all the graphs created here will be saved.

        graph_path = "/home/Graphs"
        isExist = os.path.exists(graph_path)

        if not isExist
            os.makedirs(graph_path)

        #Final plot of CSM graph

        if np.max(np.abs(x_stage_coord)) > np.min(np.abs(x_stage_coord)):
            xlim = np.max(np.abs(x_stage_coord)) + 5000
        else:
            xlim = np.min(np.abs(x_stage_coord)) + 5000

        plt.scatter(x_stage_coord, np.abs(x_full_pixel_step), label = 'X axis', color = '#C5247F')
        plt.scatter(y_stage_coord, np.abs(y_full_pixel_step), label = 'Y axis', color = '#24c5bb')
        plt.plot(xaxis_coord, xaxis_pixel_step, label = f'X Axis Best Fit, m = {np.format_float_scientific(params_csm_x[0], 2)}', color = 'green', linewidth = 2)
        plt.plot(yaxis_coord, yaxis_pixel_step, label = f'Y Axis Best Fit, m = {np.format_float_scientific(params_csm_y[0], 2)}', color = 'red', linewidth = 2)
        plt.xlim(-xlim, xlim)
        plt.title("CSM across ROM")
        plt.xlabel("Stage Coordinate")
        plt.ylabel("Pixel/Step")
        plt.tight_layout()
        plt.legend()
        plt.grid()
        plt.savefig(graph_path)

        #ROM plot

        coord = []

        for axs in ['x', 'y']:
            for dir in ['1', '-1']:
                for i in data[axs][dir]['stage_positions']:
                    x = i['x']
                    y = i['y']
                    coord.append([x, y])

        x_coord = []
        y_coord = []

        for loop in coord:
            x_coord.append(loop[0] * csm_con * pixel_um/1000)
            y_coord.append(loop[1] * csm_con * pixel_um/1000)

        #These values set limits on the graphs to make them more readable
        ROM_lim_x = abs(rom_x) - 2
        ROM_lim_y = abs(rom_y) - 2

        plt.scatter(x_coord, y_coord, color = '#C5247F')
        plt.errorbar(x_coord, y_coord, xerr=rom_err_x_mm, yerr=rom_err_y_mm, fmt="None")
        plt.title('Stage Position')
        plt.xlim(-ROM_lim_x, ROM_lim_x)
        plt.ylim(-ROM_lim_y, ROM_lim_y)
        plt.xlabel('X-Position\n(mm)')
        plt.ylabel('Y-Position\n(mm)')
        plt.tight_layout()
        plt.grid()
        plt.savefig(graph_path)

        #Polarity plot

        x_fit = np.arange(np.min(x_pos), np.max(x_pos), 1)
        y_fit = parabola(x_fit, params[0], params[1], params[2])

        plt.title(f'Polarity - {curvature}')
        plt.scatter(x_pos,z_pos, color = '#C5247F')
        plt.plot(x_fit, y_fit, color = 'green')
        plt.xlim(-xlim, xlim)
        plt.xlabel('X Position')
        plt.ylabel('Z Position')
        plt.tight_layout()
        plt.grid()
        plt.savefig(graph_path)

    def pdf_generator(self):
        with PdfPages('Calibration_Results.pdf') as pdf:

class RecentringThing(Thing):
    @thing_action
    def recentre(
        self,
        autofocus: AutofocusDep,
        stage: StageDep,
        cam: CamDep,
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

        filepath = "/var/openflexure/"

        centre = list(stage.position.values())

        # A list of all the positions we've focused
        focused_pos = [[], []]

        autofocus.looping_autofocus()

        logging.info(f"The intervals between steps is {dx}.")
        logging.info(f"Starting position is {centre}")

        results = {"Interval": dx}

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

                if len(focused_pos[direction]) > 6:
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

        results["Calculated Centre"] = centre

        with open(f"/var/openflexure/recentre_results{i}.json", 'w') as file_object:
            json.dump(results, file_object, indent = 3)

        return focused_pos
