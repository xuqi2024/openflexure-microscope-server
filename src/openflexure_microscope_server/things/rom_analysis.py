import numpy as np
import pprint
import json
from matplotlib import pyplot as plt
from PIL import Image
from scipy.optimize import curve_fit
from mpl_toolkits import mplot3d
from scipy import stats
from scipy.stats import norm
from matplotlib.backends.backend_pdf import PdfPages
from openflexure_microscope_server.things.auto_recentre_stage import get_pixel_step

csm_con = get_pixel_step()
pixel_um = 0.921
'''
Pixel_um depends on the magnification and the gear ratio. This would be determined based on
what the user selects as part of the initial setup.
'''

class PDFBlob(Blob):
    media_type: str = "application/pdf"

graph_path = "/var/openflexure/"

def straight_line(x:float, m:float, c:float) -> float:
    '''
    Straight line function.
    '''
    return m*x + c

def parabola(x:float, a:float, b:float, c:float) -> float:
    '''
    Quadratic function.
    '''
    return a * (x**2) + (b*x) + c

def plot_function(
        title: str, 
        xlabel: str, 
        ylabel: str
        ):
    """
    Initialises the basics of any plot. Add any features or customisations immediately below function.
    """
    plt.figure()
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.grid()

def pattern_gen(max_index:int, first_index:int) -> int:
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

def estimated_centre(data:dict) -> float:
    '''
    Calculates the centre position of each axis and returns coordinates.
    '''
    x_middle = (data['x']['1']['final_position']['x'] + data['x']['-1']['final_position']['x'])/2
    y_middle = (data['y']['1']['final_position']['y'] + data['y']['-1']['final_position']['y'])/2
    return [x_middle, y_middle]

def calculate_rom(data:dict) -> float:
    '''
    Calculates the range of motion.
    '''
    rom_x_steps = (data['x']['1']['final_position']['x'] - data['x']['-1']['final_position']['x'])
    rom_y_steps = (data['y']['1']['final_position']['y'] - data['y']['-1']['final_position']['y'])

    rom_x_mm = round(((rom_x_steps) * pixel_um * csm_con /1000), 2)
    rom_y_mm = round(((rom_y_steps) * pixel_um * csm_con /1000), 2)
    return [[rom_x_mm, rom_y_mm],[rom_x_steps, rom_y_steps]]

def get_stage_positions(data:dict, axis:str, key:str):
    '''
    Extracts a single coordinate variable (x, y or z) from each stage coordinate in a dataset.
    '''
    return [pos[key] for d in ['1', '-1'] for pos in data[axis][d]['stage_positions']]

def find_polarity(data:dict, dir:str) -> str:
    '''
    Determines the polarity of the z stepper motor by fitting a curve of the x and z positions along a single axis.
    '''
    x_pos = get_stage_positions(data, dir, dir)
    z_pos = get_stage_positions(data, dir, 'z')
    params, _ = curve_fit(parabola, x_pos, z_pos)
    coef = 2 * params[0]
    curvature = 'positive' if coef > 0 else 'negative' if coef < 0 else 'ERROR'
    return curvature, params, x_pos, z_pos

def extract_differences(data:dict) -> dict:
    '''
    Populates stage_dic dictionary for csm analysis. This dictionary contatins all the differences in
    stage positions where we also have a correlation.
    '''
    dif_dic, stage_dic = {}, {}
    for axis in ['x', 'y']:
        dif_dic[axis], stage_dic[axis] = {}, {}
        for d in ['1', '-1']:
            sp = data[axis][d]['stage_positions']
            dif_array = [sp[i + 1][axis] - sp[i][axis] for i in range(len(sp) - 1)]
            dif_dic[axis][d] = dif_array

            cor_idx = pattern_gen(len(dif_array), 0)
            stage_dic[axis][d] = [dif_array[i] for i in cor_idx]
    return stage_dic

def extract_positions(data:dict) -> dict:
    '''
    Populates pos_dic dictionary for csm analysis. This dictionary extracts all the x and y coordinates
    for positions where we also have a correlation.
    '''
    pos_dic = {}
    for axis in ['x', 'y']:
        pos_dic[axis] = {}
        for d in ['1', '-1']:
            sp = data[axis][d]['stage_positions']
            cor_idx = pattern_gen(len(sp), 1)
            pos_dic[axis][d] = [sp[i][axis] for i in cor_idx]
    return pos_dic

def extract_correlations(data:dict) -> dict:
    '''
    Populates cor_dic dictionary for csm analysis. This dictionary extracts all the correlation values at each
    position for the axis we are interested in.
    '''
    cor_dic = {}
    for axis in ['x', 'y']:
        cor_dic[axis] = {}
        axis_idx = 1 if axis == 'x' else 0
        for d in ['1', '-1']:
            cor_dic[axis][d] = [corr[axis_idx] for corr in data[axis][d]['correlation_lateral_steps']]
    return cor_dic

def flatten_dict(dic:str, axis:str, trim:bool=False):
    '''
    Combines two keys of a dictionary into one array. Removes last entry if trim = true
    '''
    if trim:
        return np.concatenate((np.array(dic[axis]['1'][:-1]), np.array(dic[axis]['-1'][:-1])))
    return np.concatenate((np.array(dic[axis]['1']), np.array(dic[axis]['-1'])))

def csm_analysis(stage_dic:dict, pos_dic:dict, cor_dic:dict) -> dict:
    '''
    Completes the csm analysis. First creates all the necessary arrays and returns parameters from
    curve fit.
    '''
    x_stage = flatten_dict(stage_dic, 'x', trim=False)
    y_stage = flatten_dict(stage_dic, 'y', trim=False)
    x_stage_fit = flatten_dict(stage_dic, 'x', trim=True)
    y_stage_fit = flatten_dict(stage_dic, 'y', trim=True)
    x_pos = flatten_dict(pos_dic, 'x', trim=False)
    y_pos = flatten_dict(pos_dic, 'y', trim=False)
    x_pos_fit = flatten_dict(pos_dic, 'x', trim=True)
    y_pos_fit = flatten_dict(pos_dic, 'y', trim=True)
    x_cor = flatten_dict(cor_dic, 'x', trim=False)
    y_cor = flatten_dict(cor_dic, 'y', trim=False)
    x_cor_fit = flatten_dict(cor_dic, 'x', trim=True)
    y_cor_fit = flatten_dict(cor_dic, 'y', trim=True)

    x_pixel_step = x_cor/x_stage
    y_pixel_step = y_cor/y_stage

    x_pixel_step_fit = x_cor_fit/x_stage_fit
    y_pixel_step_fit = y_cor_fit/y_stage_fit

    params_x, _ = curve_fit(straight_line, x_stage_fit, np.abs(x_pixel_step_fit))
    params_y, _ = curve_fit(straight_line, y_stage_fit, np.abs(y_pixel_step_fit))

    return {
    'x_var': np.var(x_pixel_step),
    'y_var': np.var(y_pixel_step),
    'x_std': np.std(x_pixel_step),
    'y_std': np.std(y_pixel_step),
    'params_x': params_x,
    'params_y': params_y
    }    

def compute_rom_error(cor_dic:dict) -> float:
    '''
    Carries out error analysis for range of motion.
    '''
    x_small = np.concatenate((cor_dic['x']['1'][4:], cor_dic['x']['-1'][4:]))
    y_small = np.concatenate((cor_dic['y']['1'][4:], cor_dic['y']['-1'][4:]))
    err_x = np.std(x_small)
    err_y = np.std(y_small)
    return err_x * pixel_um / 1000, err_y * pixel_um / 1000

def rom_analysis():
    filename = '/var/openflexure/settings/range_of_motion/settings.json'

        with open(filename, 'r') as file:
            data = json.load(file)

    est_centre = estimated_centre(data)
    rom = calculate_rom(data)
    curvature, params, x_pos, z_pos = find_polarity(data, 'x')
    stage_dic = extract_differences(data)
    pos_dic = extract_positions(data)
    cor_dic = extract_correlations(data)
    csm_dic = csm_analysis(stage_dic, pos_dic, cor_dic)
    rom_err_x, rom_err_y = compute_rom_error(cor_dic)

    rom_analysis_dic = {
        'Estimated Centre': est_centre,
        'Range of Motion': rom,
        'Curvature': curvature,
        'Camera to Stage Mapping': csm_dic,
        'ROM Errors': [rom_err_x, rom_err_y]
    }

    #Check for and create if necessary, a folder called Graphs where all the graphs created here will be saved.

    isExist = os.path.exists(graph_path)

    if not isExist:
        os.makedirs(graph_path)

    #CSM Graph

    if np.max(np.abs(x_pos)) > np.min(np.abs(x_pos)):
            xlim = np.max(np.abs(x_pos)) + 5000
    else:
        xlim = np.min(np.abs(x_pos)) + 5000

    plot_function("CSM across ROM", "Stage Coordinate", "Pixel/Step")
    plt.scatter(x_pos, np.abs(x_pixel_step), label = 'X axis', color = '#C5247F')
    plt.scatter(y_pos, np.abs(y_pixel_step), label = 'Y axis', color = '#24c5bb')
    plt.plot(xaxis_coord, xaxis_pixel_step, label = f'X Axis Best Fit, m = {np.format_float_scientific(csm_dic['params_x'][0], 2)}', color = 'green', linewidth = 2)
    plt.plot(yaxis_coord, yaxis_pixel_step, label = f'Y Axis Best Fit, m = {np.format_float_scientific(csm_dic['params_x'][0], 2)}', color = 'red', linewidth = 2)
    plt.xlim(-xlim, xlim)
    plt.legend()
    plt.savefig(f"{graph_path}/csm_graph.jpg")

    #ROM Plot

    coord = []

    for axs in ['x', 'y']:
        for dir in ['1', '-1']:
            for i in data['rom_data'][axs][dir]['stage_positions']:
                x = i['x']
                y = i['y']
                coord.append([x, y])

    x_coord = []
    y_coord = []

    for loop in coord:
        x_coord.append(loop[0] * pixel_per_step * pixel_um/1000)
        y_coord.append(loop[1] * pixel_per_step * pixel_um/1000)

    #These values set limits on the graphs to make them more readable
    ROM_lim_x = abs(rom_x) - 2
    ROM_lim_y = abs(rom_y) - 2
    
    plot_function('Stage Position', 'X-Position\n(mm)', 'Y-Position\n(mm)')
    plt.scatter(x_coord, y_coord, color = '#C5247F')
    plt.errorbar(x_coord, y_coord, xerr=rom_err_x, yerr=rom_err_y, fmt="None")
    plt.xlim(-ROM_lim_x, ROM_lim_x)
    plt.ylim(-ROM_lim_y, ROM_lim_y)
    plt.savefig(f"{graph_path}/rom_graph.jpg")

    #Polarity Plot

    x_fit = np.arange(np.min(x_pos), np.max(x_pos), 1)
    y_fit = quadratic(x_fit, params[0], params[1], params[2])

    plot_function(f'Polarity - {curvature}', 'X Position', 'Z Position')
    plt.scatter(x_pos,z_pos, color = '#C5247F')
    plt.plot(x_fit, y_fit, color = 'green')
    plt.xlim(-xlim, xlim)
    plt.savefig(f"{graph_path}/pol_graph.jpg")

    return rom_analysis_dic

def json_generator():
    '''
    Creates a json file with all the useful calibration data.
    This pulls together all of the settings.json files for each calibration step.
    '''
    csm_file = '/var/openflexure/settings/camera_stage_mapping/settings.json'
    with open(csm_file) as f:
        csm_object = json.load(f)

    rom_file = '/var/openflexure/settings/range_of_motion/settings.json'
    with open(rom_file) as f:
        rom_object = json.load(f)

    full_calibration = {}
    full_calibration['CSM'] = csm_object
    full_calibration['ROM'] = rom_object

    return full_calibration

def txt_sweeper():
    '''
    Opens and extracts information from a text file.
    '''
    txt_path = '/var/openflexure/assembly_config.txt'

    with open(txt_path, 'r') as f:
        txt_file = f.read().split(',')
    
    return txt_file

@thing_action
def calibration_data_generate():
    '''
    Creates a pdf containing all the useful calibration data a user would need.
    '''
    tempdir = tempfile.TemporaryDirectory()
    rom_dict = self.rom_analysis()
    calibration_data = self.json_generator()

    pixel_per_step = get_pixel_step()

    data_page = plt.figure(figsize=(11.69,8.27))
    data_page.clf()
    data_txt = (f'CSM Matrix:[[1,0],[0,1]]\n'
        f'Pixel/Step:{pixel_per_step}\n'
        f'Range of Motion(Steps):{rom_dict["x_rom(steps)"]} X {rom_dict["x_rom(steps)"]}\n'
        f'Range of Motion(mm):{rom_dict["x_rom(mm)"]} X {rom_dict["y_rom(mm)"]}'
        )
    data_page.text(0.5,0.5,data_txt, transform=data_page.transFigure, size=24, ha="center")
    data_page.savefig(f'{graph_path}/data_page.jpg')

    txt_file = self.txt_sweeper()

    config_page = plt.figure(figsize=(11.69,8.27))
    config_page.clf()
    config_txt = (f'Gear Ratio: {txt_file[0]}\n'
        f'Stage: {txt_file[1]}\n'
        f'Camera: {txt_file[2]}\n'
        f'Printer: {txt_file[3]}\n'
        f'Filament: {txt_file[4]}\n'
        f'Magnification: {txt_file[5]}\n'
        f'Temperature: {txt_file[6]}'
        )
    config_page.text(0.5,0.5,config_txt, transform=config_page.transFigure, size=24, ha="center")
    config_page.savefig(f'{graph_path}/config_page.jpg')

    graph_imgs = [
        Image.open(f"{graph_path}/{f}") for f in ["config_page.jpg", "data_page.jpg", "csm_graph.jpg", "rom_graph.jpg", "pol_graph.jpg"]
    ]

    pdf_path = f"{tempdir.name}/calibration_summary.pdf"

    graph_imgs[0].save(pdf_path, "PDF", resoultion=100, save_all=True, append_images=graph_imgs[1:])

    return PDFBlob.from_temporary_directory(tempdir, "calibration_summary.pdf")