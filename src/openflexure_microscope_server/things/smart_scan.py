import cv2
import numpy as np
import os
import time
from PIL import Image
from scipy.stats import norm
import pprint
import logging
from copy import deepcopy

from labthings_fastapi.thing import Thing
from labthings_fastapi.dependencies.thing import direct_thing_client_dependency
from labthings_fastapi.decorators import thing_action
from labthings_sangaboard import SangaboardThing
from labthings_picamera2.thing import StreamingPiCamera2
from openflexure_microscope_server.things.autofocus import AutofocusThing
from openflexure_microscope_server.things.camera_stage_mapping import CameraStageMapper
from openflexure_microscope_server.things.auto_recentre_stage import RecentringThing
from openflexure_microscope_server.things.settings_manager import SettingsManager

StageDep = direct_thing_client_dependency(SangaboardThing, "/stage/")
CamDep = direct_thing_client_dependency(StreamingPiCamera2, "/camera/")
CSMDep = direct_thing_client_dependency(CameraStageMapper, "/camera_stage_mapping/")
AutofocusDep = direct_thing_client_dependency(AutofocusThing, "/autofocus/")
RecentreStage = direct_thing_client_dependency(RecentringThing, "/auto_recentre_stage/")
SettingsDep = direct_thing_client_dependency(SettingsManager, "/settings/")

def check_dist(image, stats_list, multiple):
    '''tests whether each pixel in image is within multiple stdevs (stats_list[1]) of the mean (stats_list[0]) for all three channels
    returns a mask with True for pixels within that range (similar to stats list) and False otherwise
    '''
    return(
        np.all(np.abs(image - stats_list[np.newaxis, np.newaxis, 0, :]) < stats_list[np.newaxis, np.newaxis, 1, :] * multiple, axis = 2)
    )

def closest(current, focused_path):
    ''' Finds the index of the closest x-y position in a list from the current position,
    with ties split by the later element in the list (most recently taken)
    
    must be float64 to deal with the huge numbers involved!'''
    
    current_pos = np.array(current[:2], dtype='float64')
    path_pos = np.asarray(focused_path, dtype='float64').T[:2].T

    dist_2 = np.sqrt(np.sum((path_pos - current_pos)**2, axis=1, dtype='float64'), dtype = 'float64')
    min_dist = np.argmin(dist_2)
    mask = np.where(dist_2 == dist_2[min_dist], 1, 0)
    try:
        closest = np.max(np.nonzero(mask))
    except:
        closest = 0
    return closest 

def unpack_autofocus(scan_data):
    """Extract z, sharpness data from a move_and_measure call
    
    Data will start at `start_index`, i.e. `start_index` points are dropped
    from the beginning of the array.
    """
    jpeg_times = scan_data['jpeg_times']
    jpeg_sizes = scan_data['jpeg_sizes']
    jpeg_sizes_MB = [x / 10**3 for x in jpeg_sizes]
    stage_times = scan_data['stage_times']
    stage_positions = scan_data['stage_positions']
    stage_height = [pos[2] for pos in stage_positions]

    jpeg_heights = np.interp(jpeg_times,stage_times,stage_height)

    def turningpoints(lst):
        dx = np.diff(lst)
        return dx[1:] * dx[:-1] < 0

    turning = np.where(turningpoints(jpeg_heights))[0]+1

    return jpeg_heights[turning[0]:turning[1]], jpeg_sizes_MB[turning[0]:turning[1]]

def limit_focus_change(prev_pos, prev_z, new_pos, new_z, limit):
    # limit is the largest ratio of change in z to change in xy that's allowed

    prev_xy = np.asarray(prev_pos, dtype = 'float64')
    new_xy = np.asarray(new_pos, dtype = 'float64')

    dist = np.sqrt(np.sum(((new_xy - prev_xy)/10**4)**2, dtype = 'float64'))

    focus_change = abs(new_z - prev_z)/10**4
    if dist == 0:
        print(f'Not moved between {prev_pos} and {new_pos}')
        movement_ratio = 0
    else:
        movement_ratio = np.divide(focus_change, dist, dtype='float64')

    # print('Movement ratio is {0} in z per lateral step. The limit is {1}'.format(round(movement_ratio, 4), round(limit,4)))
    # print(f'This is the distance between {prev_pos}, {prev_z} and {new_pos}, {new_z}')

    if movement_ratio > limit:
        return 'reject'
    else:
        return 'accept'

def distance_to_site(current, next):
    current = np.array(current, dtype='float64') 
    next = np.array(next, dtype='float64')
    if (next[1] - current[1])**2 + (next[0] - current[0])**2 < 0:
        print(f'Negative distance between {next} and {current}')
    return np.sqrt((next[1] - current[1])**2 + (next[0] - current[0])**2, dtype='float64')

# def set_template(microscope, pos):
#     microscope.move(pos)
#     background = microscope.grab_image_array()
#     background_LUV = cv2.cvtColor(background, cv2.COLOR_RGB2LUV)

#     ch1 = (background_LUV.T[0]).flatten()
#     ch2 = (background_LUV.T[1]).flatten()
#     ch3 = (background_LUV.T[2]).flatten()

#     points = np.array([np.asarray(ch1),np.asarray(ch2),np.asarray(ch3)]).T

#     # we get the mean and standard deviation of values in each channel

#     mu, std = np.apply_along_axis(norm.fit, 0, points)
#     stats_list = np.vstack([mu, std])
#     return stats_list

def distance_to_site(current, next):
    next = np.array(next, dtype='float64')
    current = np.array(current, dtype='float64')
    return np.sqrt( (next[1] - current[1])**2 + (next[0] - current[0])**2 )

class SmartScanThing(Thing):
    @thing_action
    def set_template(self, settings: SettingsDep, cam: CamDep):
        background = cam.grab_jpeg()
        background = np.array(Image.open(background.open()))

        # we're working in the LUV colourspace as it collect colours together in a human-intuitive way
        background_LUV = cv2.cvtColor(background, cv2.COLOR_RGB2LUV)

        ch1 = (background_LUV.T[0]).flatten()
        ch2 = (background_LUV.T[1]).flatten()
        ch3 = (background_LUV.T[2]).flatten()

        points = np.array([np.asarray(ch1),np.asarray(ch2),np.asarray(ch3)]).T

        # we get the mean and standard deviation of values in each channel

        mu, std = np.apply_along_axis(norm.fit, 0, points)
        stats_list = np.vstack([mu, std])

        settings.update_external_metadata(data = {"background_stats": stats_list.tolist()})

        current_keys = settings.external_metadata_in_state
        logging.info(type(current_keys))

        # if "1background_stats" not in current_keys:
        current_keys.append("background_stats")
        settings.external_metadata_in_state = current_keys

        logging.info(settings.external_metadata_in_state)
        logging.info(settings.external_metadata)
    
    @thing_action
    def sample_scan(self, autofocus: AutofocusDep, stage: StageDep, cam: CamDep, csm: CSMDep, settings: SettingsDep, recentre: RecentreStage):
        # try:
        stats_list = np.array(settings.external_metadata['background_stats'])
        #     print(stats_list)
        # except:
        #     logging.warning("No template set")
        #     raise Exception

        previous_dir = 0

        # if necessary, move to the starting point for your scan

        starting_loc = list(stage.position.values())

        recentre.looping_autofocus()

        dx = 60
        dy = 60

        r = cam.grab_jpeg()
        arr = np.array(Image.open(r.open()))

        camera_stage_mapping_matrix = csm.image_to_stage_displacement_matrix

        #TODO: CHECK HOW TO GET CALIBRATION IMAGE SIZE

        dx = dx * arr.shape[1] / 100
        dy = dy * arr.shape[0] / 100

        dx = np.array(np.dot(np.array([0,dx]), camera_stage_mapping_matrix), dtype=int)[0]
        dy = np.array(np.dot(np.array([dy,0]), camera_stage_mapping_matrix), dtype=int)[1]

        dz = 3000

        sample_coverage = 7

        print(dx, dy)

        # construct a 2D scan path
        path = [[stage.position['x'], stage.position['y']]]

        # a list of the sites images have been taken at, and sites with a successful autofocus
        focused_path = []
        true_path = []

        i = 0

        ids = []

        start_time = time.strftime("%H_%M_%S-%d_%m_%Y")

        folder_path = r'scans'

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        j = 0
        while os.path.exists(os.path.join(folder_path, str(j))):
            j += 1
        folder_path = os.path.join(folder_path, str(j))
        os.makedirs(folder_path)

        # move to each x-y position. in z, move to the height of the closest x-y position that successfully focused
        while len(path) > 0:
            loc = [path[0][0], path[0][1], stage.position['z']]

            path.remove(loc[:2])

            stage.move_absolute(x = int(loc[0]), y = int(loc[1]), z = int(loc[2]))

            if len(focused_path) > 1:
                z_index = closest(loc, focused_path)
                # print('Moving to {0}'.format([coords[0], coords[1], focused_path[z_index][2]]))
                # print(focused_path)
                stage.move_absolute(x = int(loc[0]), y = int(loc[1]), z = int(focused_path[z_index][2]))

            # capture an image, convert it to LUV, then make lists of the 3 channels' values
            img = cam.grab_jpeg()
            img = np.array(Image.open(img.open()))

            img2 = cv2.cvtColor(img, cv2.COLOR_RGB2LUV)
            ch4 = (img2.T[0]).flatten()
            ch5 = (img2.T[1]).flatten()
            ch6 = (img2.T[2]).flatten()

            # mask the image to only include pixels outside 5 stds of the mean of all three channels.
            # get the percent of pixels that are in the mask (assumed sample)
            img_mask = check_dist(img2, stats_list, 5)
            background_coverage = round(100*np.count_nonzero(img_mask)/img_mask.size, 1)


            # if more than 92% of the image is background, treat it as background and continue

            if 100 - background_coverage < sample_coverage:
                category = 'background'
                # fig.set_facecolor("gray")
            else:
                # if not, it's sample. run an autofocus and use the updated height
                new_pos = [[stage.position['x'] - dx, stage.position['y']], [stage.position['x'] + dx, stage.position['y']], [stage.position['x'], stage.position['y'] - dy], [stage.position['x'], stage.position['y'] + dy]]
                for pos in new_pos:
                    if pos not in [sublist[:2] for sublist in true_path] and pos not in path:
                        path.append(pos)

                category = 'sample'
                # fig.set_facecolor("pink")

                attempts = 0

                while True:
                    recentre.looping_autofocus(dz=3000)
                    current_height = stage.position['z']

                    # if there have been successful autofocuses in this scan, find the closest one in x-y
                    # test if the change in z between them exceeds a ratio (indicating a failed autofocus)

                    if len(focused_path) > 0:
                        nearest_focused_site = focused_path[closest(loc, focused_path)]
                        result = limit_focus_change(nearest_focused_site[0:2], nearest_focused_site[-1], loc[0:2], current_height, 0.3)

                    # if there haven't been any previous autofocuses, we have to assume this one worked
                    else:
                        result = 'accept'

                    # if the autofocus worked, take a new, more focused image. add the current position to the list of successful locations
                    if result == 'accept':
                        loc = list(stage.position.values())
                        # img = microscope.grab_image_array()
                        focused_path.append(loc)
                        break
                    else:
                        if attempts >= 5:
                            break
                        else:
                        # if the autofocus was rejected, we return to the height of the closest successful autofocus. not perfect, but better than wandering out of focus
                            print('Resetting from a previous focus position. Options are {0}, we chose {1}'.format(focused_path, nearest_focused_site))
                            stage.move_absolute(z = int(focused_path[z_index][2]))
                            attempts += 1

                img = Image.open(cam.capture_jpeg().open())
                exif = img.info['exif']
                # img = np.array(Image.open(img.open()))
                # img = cv2.resize(img, (0,0), fx = 0.5, fy = 0.5)
                # img = Image.fromarray(img)
                width, height = img.size 
                img = img.resize((int(width*0.5), int(height*0.5)))
                img.save(os.path.join(folder_path, f"rabbit_{loc[0]}_{loc[1]}.jpg"), exif = exif)

            img_preview = cam.grab_jpeg()
            img_preview = np.array(Image.open(img_preview.open()))
            # add the current position to the list of all positions visited
            true_path.append(loc)

            path = sorted(path, key = lambda x: distance_to_site(loc[:2], x))

            if len(true_path) > 750:
                break
        
        stage.move_absolute(x = starting_loc[0], y = starting_loc[1], z = starting_loc[2])
