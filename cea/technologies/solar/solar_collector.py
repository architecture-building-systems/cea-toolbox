"""
solar collectors
"""


import os
import time
from itertools import repeat
from math import cos, atan, sin, degrees, radians, tan, log

import geopandas as gpd
import numpy as np
import pandas as pd
from geopandas import GeoDataFrame as gdf
from numba import jit
import pvlib

import cea.config
import cea.inputlocator
import cea.utilities.parallel
from cea.constants import HOURS_IN_YEAR
from cea.technologies.solar import constants
from cea.utilities import epwreader
from cea.utilities import solar_equations
from cea.utilities.standardize_coordinates import get_lat_lon_projected_shapefile
from cea.analysis.costs.equations import calc_capex_annualized
__author__ = "Jimeno A. Fonseca"
__copyright__ = "Copyright 2015, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Jimeno A. Fonseca", "Shanshan Hsieh", "Daren Thomas"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Daren Thomas"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"


# SC heat generation

def calc_SC(locator, config, latitude, longitude, weather_data, date_local, building_name):
    """
    This function first determines the surface area with sufficient solar radiation, and then calculates the optimal
    tilt angles of panels at each surface location. The panels are categorized into groups by their surface azimuths,
    tilt angles, and global irradiation. In the last, heat generation from SC panels of each group is calculated.
    :param locator: An InputLocator to locate input files
    :type locator: cea.inputlocator.InputLocator
    :param config: cea.config
    :param latitude: latitude of the case study location
    :type latitude: float
    :param longitude: longitude of the case study location
    :type longitude: float
    :param weather_data: Data frame containing the weather data in the .epw file as per config
    :type weather_data: pandas.DataFrame
    :param date_local: contains the localized (to timezone) dates for each timestep of the year
    :param building_name: list of building names in the case study
    :type building_name: Series
    :return: Building_SC.csv with solar collectors heat generation potential of each building, Building_SC_sensors.csv
    with sensor data of each SC panel
    """

    t0 = time.perf_counter()

    type_panel = config.solar.type_SCpanel

    radiation_path = locator.get_radiation_building_sensors(building=building_name)
    metadata_csv = locator.get_radiation_metadata(building=building_name)

    # solar properties
    solar_properties = solar_equations.calc_sun_properties(latitude, longitude, weather_data, date_local, config)
    print('calculating solar properties done for building %s' % building_name)

    # get properties of the panel to evaluate
    panel_properties_SC = calc_properties_SC_db(locator.get_database_conversion_systems(), config)
    print('gathering properties of Solar collector panel for building %s' % building_name)

    # select sensor point with sufficient solar radiation
    max_annual_radiation, annual_radiation_threshold, sensors_rad_clean, sensors_metadata_clean = \
        solar_equations.filter_low_potential(radiation_path, metadata_csv, config)

    print('filtering low potential sensor points done for building %s' % building_name)

    # Calculate the heights of all buildings for length of vertical pipes
    tot_bui_height_m = gpd.read_file(locator.get_zone_geometry())['height_ag'].sum()

    # set the maximum roof coverage
    max_roof_coverage = config.solar.max_roof_coverage

    if not sensors_metadata_clean.empty:
        if not config.solar.custom_tilt_angle:
            # calculate optimal angle and tilt for panels
            sensors_metadata_cat = solar_equations.optimal_angle_and_tilt(sensors_metadata_clean, latitude,
                                                                          solar_properties, max_annual_radiation,
                                                                          panel_properties_SC, max_roof_coverage)
            print('calculating optimal tilt angle and separation done for building %s' % building_name)
        else:
            # calculate spacing required by user-supplied tilt angle for panels
            sensors_metadata_cat = solar_equations.calc_spacing_custom_angle(sensors_metadata_clean, solar_properties,
                                                                           max_annual_radiation, panel_properties_SC,
                                                                           config.solar.panel_tilt_angle,
                                                                           max_roof_coverage)
            print('calculating separation for custom tilt angle done')

        # group the sensors with the same tilt, surface azimuth, and total radiation
        sensor_groups = solar_equations.calc_groups(sensors_rad_clean, sensors_metadata_cat)

        print('generating groups of sensor points done for building %s' % building_name)

        # calculate heat production from solar collectors
        Final = calc_SC_generation(sensor_groups, weather_data, date_local, solar_properties, tot_bui_height_m,
                                   panel_properties_SC,
                                   latitude, config)

        # save SC generation potential and metadata of the selected sensors
        panel_type = panel_properties_SC['type']
        Final.to_csv(locator.SC_results(building_name, panel_type), index=True, float_format='%.2f', na_rep='nan')
        sensors_metadata_cat.to_csv(locator.SC_metadata_results(building_name, panel_type), index=True,
                                    index_label='SURFACE',
                                    float_format='%.2f', na_rep='nan')  # print selected metadata of the selected sensors

        print('Building', building_name, 'done - time elapsed:', (time.perf_counter() - t0), ' seconds')
    else:  # This loop is activated when a building has not sufficient solar potential
        panel_type = panel_properties_SC['type']
        Final = pd.DataFrame(
            {'SC_' + type_panel + '_walls_north_m2': 0, 'SC_' + type_panel + '_walls_north_Q_kWh': 0,
             'SC_' + type_panel + '_walls_north_Tout_C': 0,
             'SC_' + type_panel + '_walls_south_m2': 0, 'SC_' + type_panel + '_walls_south_Q_kWh': 0,
             'SC_' + type_panel + '_walls_south_Tout_C': 0,
             'SC_' + type_panel + '_walls_east_m2': 0, 'SC_' + type_panel + '_walls_east_Q_kWh': 0,
             'SC_' + type_panel + '_walls_east_Tout_C': 0,
             'SC_' + type_panel + '_walls_west_m2': 0, 'SC_' + type_panel + '_walls_west_Q_kWh': 0,
             'SC_' + type_panel + '_walls_west_Tout_C': 0,
             'SC_' + type_panel + '_roofs_top_m2': 0, 'SC_' + type_panel + '_roofs_top_Q_kWh': 0,
             'SC_' + type_panel + '_roofs_top_Tout_C': 0,
             'Q_SC_gen_kWh': 0, 'T_SC_sup_C': 0, 'T_SC_re_C': 0, 'mcp_SC_kWperC': 0, 'Eaux_SC_kWh': 0,
             'Q_SC_l_kWh': 0, 'Area_SC_m2': 0, 'radiation_kWh': 0,
             'Date':date_local},
            index=np.zeros(HOURS_IN_YEAR))
        Final.set_index('Date', inplace=True)
        Final.to_csv(locator.SC_results(building_name, panel_type), index=True, float_format='%.2f', na_rep='nan')
        sensors_metadata_cat = pd.DataFrame(
            {'SURFACE': 0, 'AREA_m2': 0, 'BUILDING': 0, 'TYPE': 0, 'Xcoor': 0, 'Xdir': 0, 'Ycoor': 0, 'Ydir': 0,
             'Zcoor': 0, 'Zdir': 0, 'orientation': 0, 'total_rad_Whm2': 0, 'tilt_deg': 0, 'B_deg': 0,
             'array_spacing_m': 0, 'surface_azimuth_deg': 0, 'area_installed_module_m2': 0,
             'CATteta_z': 0, 'CATB': 0, 'CATGB': 0, 'type_orientation': 0}, index=range(2))
        sensors_metadata_cat.to_csv(locator.SC_metadata_results(building_name, panel_type), index=True,
                                    float_format='%.2f', na_rep="nan")

    return


# =========================
# SC heat production
# =========================

def calc_SC_generation(sensor_groups, weather_data, date_local, solar_properties, tot_bui_height, panel_properties_SC,
                       latitude_deg, config):
    """
    To calculate the heat generated from SC panels.
    :param sensor_groups: properties of sensors in each group
    :type sensor_groups: dict
    :param weather_data: weather data read from the epw file
    :type weather_data: dataframe
    :param solar_properties:
    :param tot_bui_height: total height of all buildings [m]
    :param panel_properties_SC: properties of solar panels
    :type panel_properties_SC: dataframe
    :param latitude_deg: latitude of the case study location
    :param config: user settings from cea.config
    :return: dataframe
    """

    # local variables
    type_panel = config.solar.type_SCpanel
    number_groups = sensor_groups['number_groups']  # number of groups of sensor points
    prop_observers = sensor_groups['prop_observers']  # mean values of sensor properties of each group of sensors
    hourly_radiation = sensor_groups['hourlydata_groups']  # mean hourly radiation of sensors in each group [Wh/m2]

    T_in_C = get_t_in_sc(config)
    Tin_array_C = np.zeros(HOURS_IN_YEAR) + T_in_C

    # create lists to store results
    list_results_from_SC = [0 for i in range(number_groups)]
    list_areas_groups = [0 for i in range(number_groups)]
    total_radiation_kWh = [0 for i in range(number_groups)]
    total_mcp_kWperC = [0 for i in range(number_groups)]
    total_qloss_kWh = [0 for i in range(number_groups)]
    total_aux_el_kWh = [0 for i in range(number_groups)]
    total_Qh_output_kWh = [0 for i in range(number_groups)]

    potential = pd.DataFrame(index=range(HOURS_IN_YEAR))
    panel_orientations = ['walls_south', 'walls_north', 'roofs_top', 'walls_east', 'walls_west']
    for panel_orientation in panel_orientations:
        potential['SC_'+ type_panel + '_' + panel_orientation + '_Q_kWh'] = 0
        potential['SC_' + type_panel + '_'+ panel_orientation + '_m2'] = 0

    # calculate equivalent length of pipes
    total_area_module_m2 = prop_observers['area_installed_module_m2'].sum()  # total area for panel installation
    total_pipe_length = cal_pipe_equivalent_length(tot_bui_height, panel_properties_SC, total_area_module_m2)

    # assign default number of subsdivisions for the calculation
    if panel_properties_SC['type'] == 'ET':  # ET: evacuated tubes
        panel_properties_SC['Nseg'] = 100  # default number of subsdivisions for the calculation
    else:
        panel_properties_SC['Nseg'] = 10

    for group in range(number_groups):
        # calculate radiation types (direct/diffuse) in group
        radiation_Wperm2 = solar_equations.calc_radiation_type(group, hourly_radiation, weather_data)

        # load panel angles from each group
        teta_z_deg = prop_observers.loc[group, 'surface_azimuth_deg']  # azimuth of panels of group
        tilt_angle_deg = prop_observers.loc[group, 'B_deg']  # tilt angle of panels

        # calculate incidence angle modifier for beam radiation
        IAM_b = calc_IAM_beam_SC(solar_properties, teta_z_deg, tilt_angle_deg, panel_properties_SC['type'],
                                 latitude_deg)

        # calculate heat production from a solar collector of each group
        list_results_from_SC[group] = calc_SC_module(config, radiation_Wperm2, panel_properties_SC,
                                                     weather_data.drybulb_C.values,
                                                     IAM_b, tilt_angle_deg, total_pipe_length)

        # calculate results from each group
        panel_orientation = prop_observers.loc[group, 'type_orientation']
        module_area_per_group_m2 = prop_observers.loc[group, 'area_installed_module_m2']
        number_modules_per_group = module_area_per_group_m2 / panel_properties_SC['module_area_m2']

        SC_Q_kWh = list_results_from_SC[group][1] * number_modules_per_group

        potential['SC_' + type_panel + '_' + panel_orientation + '_Q_kWh'] = potential[
                                                                                 'SC_' + type_panel + '_' + panel_orientation + '_Q_kWh'] + SC_Q_kWh
        potential['SC_' + type_panel + '_' + panel_orientation + '_m2'] = potential[
                                                                              'SC_' + type_panel + '_' + panel_orientation + '_m2'] + module_area_per_group_m2  # assume parallel connections in this group

        # aggregate results from all modules
        list_areas_groups[group] = module_area_per_group_m2
        total_mcp_kWperC[group] = list_results_from_SC[group][5] * number_modules_per_group
        total_qloss_kWh[group] = list_results_from_SC[group][0] * number_modules_per_group
        total_aux_el_kWh[group] = list_results_from_SC[group][2] * number_modules_per_group
        total_Qh_output_kWh[group] = list_results_from_SC[group][1] * number_modules_per_group
        total_radiation_kWh[group] = (radiation_Wperm2['I_sol'] * module_area_per_group_m2 / 1000)

    potential['Area_SC_m2'] = sum(list_areas_groups)
    potential['radiation_kWh'] = sum(total_radiation_kWh).values
    potential['Q_SC_gen_kWh'] = sum(total_Qh_output_kWh)
    potential['mcp_SC_kWperC'] = sum(total_mcp_kWperC)
    potential['Eaux_SC_kWh'] = sum(total_aux_el_kWh)
    potential['Q_SC_l_kWh'] = sum(total_qloss_kWh)
    potential['T_SC_sup_C'] = Tin_array_C
    T_out_C = (potential['Q_SC_gen_kWh'] / potential['mcp_SC_kWperC']) + T_in_C
    potential[
        'T_SC_re_C'] = T_out_C if T_out_C is not np.nan else np.nan  # assume parallel connections for all panels #FIXME: change here when the flow rate is zero

    potential['Date'] = date_local
    potential = potential.set_index('Date')

    return potential


def get_t_in_sc(config):
    if config.solar.t_in_sc is not None:
        Tin_C = config.solar.T_in_SC
    else:
        if config.solar.type_SCpanel == 'FP':
            Tin_C = constants.T_IN_SC_FP
        elif config.solar.type_SCpanel == 'ET':
            Tin_C = constants.T_IN_SC_ET
    return Tin_C


def cal_pipe_equivalent_length(tot_bui_height_m, panel_prop, total_area_module):
    """
    To calculate the equivalent length of pipings in buildings
    :param tot_bui_height_m: total heights of buildings
    :type tot_bui_height_m: float
    :param panel_prop: properties of the solar panels
    :type panel_prop: dict
    :param total_area_module: total installed module area
    :type total_area_module: float
    :return: equivalent lengths of pipings in buildings
    :rtype: dict
    """

    # local variables
    lv = panel_prop['module_length_m']  # module length
    total_area_aperture = total_area_module * panel_prop['aperture_area_ratio']
    number_modules = round(total_area_module / panel_prop['module_area_m2'])  # this is an estimation

    # main calculation
    l_ext_mperm2 = (2 * lv * number_modules / total_area_aperture)  # pipe length within the collectors
    l_int_mperm2 = 2 * tot_bui_height_m / total_area_aperture  # pipe length from building substation to roof top collectors
    Leq_mperm2 = l_int_mperm2 + l_ext_mperm2  # in m/m2 aperture

    pipe_equivalent_lengths = {'Leq_mperm2': Leq_mperm2, 'l_ext_mperm2': l_ext_mperm2, 'l_int_mperm2': l_int_mperm2}

    return pipe_equivalent_lengths


def calc_SC_module(config, radiation_Wperm2, panel_properties, Tamb_vector_C, IAM_b, tilt_angle_deg, pipe_lengths):
    """
    This function calculates the heat production from a solar collector. The method is adapted from TRNSYS Type 832.
    Assume no no condensation gains, no wind or long-wave dependency, sky factor set to zero.
    :param config: user settings in cea.config
    :param radiation_Wperm2: direct and diffuse irradiation
    :type radiation_Wperm2: dataframe
    :param panel_properties: properties of SC collectors
    :type panel_properties: dict
    :param Tamb_vector_C: ambient temperatures
    :type Tamb_vector_C: Series
    :param IAM_b: incident andgle modifiers for direct(beam) radiation
    :type IAM_b: ndarray
    :param tilt_angle_deg: panel tilt angle
    :type tilt_angle_deg: float
    :param pipe_lengths: equivalent lengths of aux pipes
    :type pipe_lengths: dict
    :return:
    ..[M. Haller et al., 2012] Haller, M., Perers, B., Bale, C., Paavilainen, J., Dalibard, A. Fischer, S. & Bertram, E.
    (2012). TRNSYS Type 832 v5.00 " Dynamic Collector Model by Bengt Perers". Updated Input-Output Reference.
    ..[ J. Fonseca et al., 2016] Fonseca, J., Nguyen, T-A., Schlueter, A., Marechal, F. City Energy Analyst:
    Integrated framework for analysis and optimization of building energy systems in neighborhoods and city districts.
    Energy and Buildings, 2016.
    """

    # read variables
    Tin_C = get_t_in_sc(config)
    n0 = panel_properties['n0']  # zero loss efficiency at normal incidence [-]
    c1 = panel_properties['c1']  # collector heat loss coefficient at zero temperature difference and wind speed [W/m2K]
    c2 = panel_properties['c2']  # temperature difference dependency of the heat loss coefficient [W/m2K2]
    mB0_r = panel_properties['mB0_r']  # nominal flow rate per aperture area [kg/h/m2 aperture]
    mB_max_r = panel_properties['mB_max_r']  # maximum flow rate per aperture area
    mB_min_r = panel_properties['mB_min_r']  # minimum flow rate per aperture area
    C_eff_Jperm2K = panel_properties['C_eff']  # thermal capacitance of module [J/m2K]
    IAM_d = panel_properties['IAM_d']  # incident angle modifier for diffuse radiation [-]
    dP1 = panel_properties['dP1']  # pressure drop [Pa/m2] at zero flow rate
    dP2 = panel_properties['dP2']  # pressure drop [Pa/m2] at nominal flow rate (mB0)
    dP3 = panel_properties['dP3']  # pressure drop [Pa/m2] at maximum flow rate (mB_max)
    dP4 = panel_properties['dP4']  # pressure drop [Pa/m2] at minimum flow rate (mB_min)
    Cp_fluid_JperkgK = panel_properties['Cp_fluid']  # J/kgK
    aperature_area_ratio = panel_properties['aperture_area_ratio']  # aperature area ratio [-]
    area_sc_module = panel_properties['module_area_m2']
    Nseg = panel_properties['Nseg']

    aperture_area_m2 = aperature_area_ratio * area_sc_module  # aperture area of each module [m2]
    msc_max_kgpers = mB_max_r * aperture_area_m2 / 3600  # maximum mass flow [kg/s]

    # Do the calculation of every time step for every possible flow condition
    # get states where highly performing values are obtained.
    specific_flows_kgpers = [np.zeros(HOURS_IN_YEAR), (np.zeros(HOURS_IN_YEAR) + mB0_r) * aperture_area_m2 / 3600,
                             (np.zeros(HOURS_IN_YEAR) + mB_max_r) * aperture_area_m2 / 3600,
                             (np.zeros(HOURS_IN_YEAR) + mB_min_r) * aperture_area_m2 / 3600, np.zeros(HOURS_IN_YEAR),
                             np.zeros(HOURS_IN_YEAR)]  # in kg/s
    specific_pressure_losses_Pa = [np.zeros(HOURS_IN_YEAR), (np.zeros(HOURS_IN_YEAR) + dP2) * aperture_area_m2,
                                   (np.zeros(HOURS_IN_YEAR) + dP3) * aperture_area_m2,
                                   (np.zeros(HOURS_IN_YEAR) + dP4) * aperture_area_m2, np.zeros(HOURS_IN_YEAR),
                                   np.zeros(HOURS_IN_YEAR)]  # in Pa

    # generate empty lists to store results
    temperature_out_C = [np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR),
                         np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR)]
    temperature_in_C = [np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR),
                        np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR)]
    temperature_mean_C = [np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR),
                          np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR),
                          np.zeros(HOURS_IN_YEAR)]
    supply_out_kW = [np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR),
                     np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR)]
    supply_losses_kW = [np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR),
                        np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR)]
    auxiliary_electricity_kW = [np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR),
                                np.zeros(HOURS_IN_YEAR), np.zeros(HOURS_IN_YEAR),
                                np.zeros(HOURS_IN_YEAR)]
    supply_out_total_kW = np.zeros(HOURS_IN_YEAR)
    mcp_kWperK = np.zeros(HOURS_IN_YEAR)

    # calculate absorbed radiation
    tilt_rad = radians(tilt_angle_deg)
    q_rad_vector = np.vectorize(calc_q_rad)(n0, IAM_b, IAM_d, radiation_Wperm2.I_direct, radiation_Wperm2.I_diffuse,
                                            tilt_rad)  # absorbed solar radiation in W/m2 is a mean of the group
    for flow in range(6):
        mode_seg = 1  # mode of segmented heat loss calculation. only one mode is implemented.
        TIME0 = 0
        DELT = 1  # timestep 1 hour
        delts = DELT * 3600  # convert time step in seconds
        Tfl = np.zeros(3)  # create vector to store value at previous [1] and present [2] time-steps
        DT = np.zeros(3)
        Tabs = np.zeros(3)
        STORED = np.zeros(600)
        TflA = np.zeros(600)
        TflB = np.zeros(600)
        TabsB = np.zeros(600)
        TabsA = np.zeros(600)
        q_gain_Seg = np.zeros(101)  # maximum Iseg = maximum Nseg + 1 = 101

        for t in range(HOURS_IN_YEAR):
            Mfl_kgpers = calc_Mfl_kgpers(C_eff_Jperm2K, Cp_fluid_JperkgK, DELT, Nseg, STORED, TIME0, Tin_C,
                                         aperture_area_m2, specific_flows_kgpers[flow], t)

            Tamb_C = Tamb_vector_C[t]
            q_rad_Wperm2 = q_rad_vector[t]
            Tout_C = calc_Tout_C(Cp_fluid_JperkgK, DT, Nseg, STORED, Tabs, Tamb_C, Tfl, Tin_C, aperture_area_m2, c1,
                                 q_rad_Wperm2, Mfl_kgpers)
            # calculate q_gain with the guess for DT[1]
            q_gain_Wperm2 = calc_q_gain(Tfl, q_rad_Wperm2, DT, Tin_C, aperture_area_m2, c1, c2,
                                        Mfl_kgpers, delts, Cp_fluid_JperkgK, C_eff_Jperm2K, Tamb_C)

            A_seg_m2 = aperture_area_m2 / Nseg  # aperture area per segment

            # multi-segment calculation to avoid temperature jump at times of flow rate changes.
            Tout_Seg_C = do_multi_segment_calculation(A_seg_m2, C_eff_Jperm2K, Cp_fluid_JperkgK, DT, Mfl_kgpers, Nseg,
                                                      STORED, Tabs, TabsA, Tamb_C, Tfl, TflA, TflB, Tin_C, Tout_C, c1,
                                                      c2, delts, mode_seg, q_gain_Seg, q_gain_Wperm2, q_rad_Wperm2)

            # resulting net energy output
            q_out_kW = (Mfl_kgpers * Cp_fluid_JperkgK * (Tout_Seg_C - Tin_C)) / 1000  # [kW]
            Tabs[2] = 0
            # storage of the mean temperature
            for Iseg in range(1, Nseg + 1):
                STORED[200 + Iseg] = TflB[Iseg]
                STORED[400 + Iseg] = TabsB[Iseg]
                Tabs[2] = Tabs[2] + TabsB[Iseg] / Nseg

            # outputs
            temperature_out_C[flow][t] = Tout_Seg_C
            temperature_in_C[flow][t] = Tin_C
            supply_out_kW[flow][t] = q_out_kW
            temperature_mean_C[flow][t] = (Tin_C + Tout_Seg_C) / 2  # Mean absorber temperature at present

            # the following lines do not perform meaningful operation, the iteration on DT are performed in calc_q_gain
            # these lines are kept here as a reference to the original model in FORTRAN
            # q_gain = 0
            # TavgB = 0
            # TavgA = 0
            # for Iseg in range(1, Nseg + 1):
            #     q_gain = q_gain + q_gain_Seg[Iseg] * A_seg_m2  # [W]
            #     TavgA = TavgA + TflA[Iseg] / Nseg
            #     TavgB = TavgB + TflB[Iseg] / Nseg
            # # OUT[9] = q_gain/Area_a # in W/m2
            # OUT[11] = q_mtherm
            # OUT[12] = q_balance_error
        if flow < 4:
            auxiliary_electricity_kW[flow] = vectorize_calc_Eaux_SC(specific_flows_kgpers[flow],
                                                                    specific_pressure_losses_Pa[flow], pipe_lengths,
                                                                    aperture_area_m2)  # in kW
        if flow == 3:
            q1 = supply_out_kW[0]
            q2 = supply_out_kW[1]
            q3 = supply_out_kW[2]
            q4 = supply_out_kW[3]
            E1 = auxiliary_electricity_kW[0]
            E2 = auxiliary_electricity_kW[1]
            E3 = auxiliary_electricity_kW[2]
            E4 = auxiliary_electricity_kW[3]
            # calculate optimal mass flow and the corresponding pressure loss
            specific_flows_kgpers[4], specific_pressure_losses_Pa[4] = calc_optimal_mass_flow(q1, q2, q3, q4, E1, E2,
                                                                                              E3, E4, 0,
                                                                                              mB0_r, mB_max_r, mB_min_r,
                                                                                              0,
                                                                                              dP2, dP3, dP4,
                                                                                              aperture_area_m2)
        if flow == 4:
            # calculate pumping electricity when operates at optimal mass flow
            auxiliary_electricity_kW[flow] = vectorize_calc_Eaux_SC(specific_flows_kgpers[flow],
                                                                    specific_pressure_losses_Pa[flow], pipe_lengths,
                                                                    aperture_area_m2)  # in kW
            dp5 = specific_pressure_losses_Pa[flow]
            q5 = supply_out_kW[flow]
            m5 = specific_flows_kgpers[flow]
            # set flow rate to zero when supply_out_kW is negative
            specific_flows_kgpers[5], specific_pressure_losses_Pa[5] = calc_optimal_mass_flow_2(m5, q5, dp5)

        if flow == 5:  # optimal mass flow
            supply_losses_kW[flow] = np.vectorize(calc_qloss_network)(specific_flows_kgpers[flow],
                                                                      pipe_lengths['l_ext_mperm2'],
                                                                      aperture_area_m2,
                                                                      temperature_mean_C[flow], Tamb_vector_C,
                                                                      msc_max_kgpers)
            auxiliary_electricity_kW[flow] = vectorize_calc_Eaux_SC(specific_flows_kgpers[flow],
                                                                    specific_pressure_losses_Pa[flow],
                                                                    pipe_lengths, aperture_area_m2)  # in kW
            supply_out_total_kW = supply_out_kW[flow].copy() + 0.5 * auxiliary_electricity_kW[flow].copy() - \
                                  supply_losses_kW[flow].copy()  # eq.(58) _[J. Fonseca et al., 2016]
            mcp_kWperK = specific_flows_kgpers[flow] * (Cp_fluid_JperkgK / 1000)  # mcp in kW/K

            update_negative_total_supply(aperture_area_m2, auxiliary_electricity_kW, flow, mcp_kWperK, pipe_lengths,
                                         specific_flows_kgpers, specific_pressure_losses_Pa, supply_losses_kW,
                                         supply_out_total_kW)

    result = [supply_losses_kW[5], supply_out_total_kW, auxiliary_electricity_kW[5], temperature_out_C[5],
              temperature_in_C[5], mcp_kWperK]

    return result


@jit(nopython=True)
def do_multi_segment_calculation(A_seg_m2, C_eff_Jperm2K, Cp_fluid_JperkgK, DT, Mfl_kgpers, Nseg, STORED,
                                 Tabs, TabsA, Tamb_C, Tfl, TflA, TflB, Tin_C, Tout_C, c1, c2, delts,
                                 mode_seg, q_gain_Seg, q_gain_Wperm2, q_rad_Wperm2):
    Tout_Seg_C = 0.0  # this value will be overwritten after first iteration
    for Iseg in range(1, Nseg + 1):
        # get temperatures of the previous time-step
        TflA[Iseg] = STORED[100 + Iseg]
        TabsA[Iseg] = STORED[300 + Iseg]
        if Iseg > 1:
            Tin_Seg_C = Tout_Seg_C
        else:
            Tin_Seg_C = Tin_C

        if Mfl_kgpers > 0 and mode_seg == 1:  # same heat gain/ losses for all segments
            Tout_Seg_K = ((Mfl_kgpers * Cp_fluid_JperkgK * (Tin_Seg_C + 273.15)) / A_seg_m2 -
                          (C_eff_Jperm2K * (Tin_Seg_C + 273.15)) / (2 * delts) + q_gain_Wperm2 +
                          (C_eff_Jperm2K * (TflA[Iseg] + 273.15) / delts)) / (
                                 Mfl_kgpers * Cp_fluid_JperkgK / A_seg_m2 + C_eff_Jperm2K / (2 * delts))
            Tout_Seg_C = Tout_Seg_K - 273.15  # in [C]
            TflB[Iseg] = (Tin_Seg_C + Tout_Seg_C) / 2
        else:  # heat losses based on each segment's inlet and outlet temperatures.
            Tfl[1] = TflA[Iseg]
            Tabs[1] = TabsA[Iseg]
            q_gain_Wperm2 = calc_q_gain(Tfl, q_rad_Wperm2, DT, Tin_Seg_C, A_seg_m2, c1, c2,
                                        Mfl_kgpers, delts, Cp_fluid_JperkgK, C_eff_Jperm2K, Tamb_C)
            Tout_Seg_C = Tout_C

            if Mfl_kgpers > 0:
                TflB[Iseg] = (Tin_Seg_C + Tout_Seg_C) / 2
                Tout_Seg_C = TflA[Iseg] + (q_gain_Wperm2 * delts) / C_eff_Jperm2K
            else:
                TflB[Iseg] = Tout_Seg_C

            # the following lines do not perform meaningful operation, the iteration on DT are performed in calc_q_gain
            # these lines are kept here as a reference to the original model in FORTRAN
            # q_fluid_Wperm2 = (Tout_Seg_C - Tin_Seg_C) * Mfl_kgpers * Cp_fluid_JperkgK / A_seg_m2
            # q_mtherm_Whperm2 = (TflB[Iseg] - TflA[
            #     Iseg]) * C_eff_Jperm2K / delts  # total heat change rate of thermal capacitance
            # q_balance_error = q_gain_Wperm2 - q_fluid_Wperm2 - q_mtherm_Whperm2
            # # assert abs(q_balance_error) > 1, "q_balance_error in solar-collector calculation"
        q_gain_Seg[Iseg] = q_gain_Wperm2  # in W/m2
    return Tout_Seg_C


@jit(nopython=True)
def calc_Tout_C(Cp_fluid_JperkgK, DT, Nseg, STORED, Tabs, Tamb_C, Tfl, Tin_C, aperture_area_m2, c1,
                q_rad_Wperm2, Mfl_kgpers):
    # calculate mean fluid temperature and average absorber temperature at the beginning of the time-step

    Tfl[1] = 0  # mean fluid temperature from the last timestep
    Tabs[1] = 0  # mean absorber temperature from the last timestep
    for Iseg in range(1, Nseg + 1):
        Tfl[1] = Tfl[1] + STORED[100 + Iseg] / Nseg  # mean fluid temperature
        Tabs[1] = Tabs[1] + STORED[300 + Iseg] / Nseg  # mean absorber temperature
    ## first guess for DT[1] (T,fluid - T,ambient)
    if Mfl_kgpers > 0:
        Tout_C = Tin_C + (q_rad_Wperm2 - (c1 + 0.5) * (Tin_C - Tamb_C)) / (
                Mfl_kgpers * Cp_fluid_JperkgK / aperture_area_m2)
        Tfl[2] = (Tin_C + Tout_C) / 2  # mean fluid temperature at present time-step
    else:
        Tout_C = Tamb_C + q_rad_Wperm2 / (c1 + 0.5)
        Tfl[2] = Tout_C  # fluid temperature same as outlet temperature
    DT[1] = Tfl[2] - Tamb_C  # difference between mean fluid temperature and the ambient temperature
    return Tout_C


@jit(nopython=True)
def calc_Mfl_kgpers(C_eff_Jperm2K, Cp_fluid_JperkgK, DELT, Nseg, STORED, TIME0, Tin_C, aperture_area_m2,
                    specific_flows_kgpers, time):
    Mfl_kgpers = specific_flows_kgpers[time]  # [kg/s]
    if time < TIME0 + DELT / 2:
        # set output values to the appropriate initial values
        for Iseg in range(101, 501):  # 400 points with the data
            STORED[Iseg] = Tin_C
    else:
        # write average temperature of all segments at the end of previous time-step
        # as the initial temperature of the present time-step
        for Iseg in range(1, Nseg + 1):  # 400 points with the data
            STORED[100 + Iseg] = STORED[200 + Iseg]  # thermal capacitance node temperature
            STORED[300 + Iseg] = STORED[400 + Iseg]  # absorber node temperature
    # calculate stability criteria
    if Mfl_kgpers > 0:
        stability_criteria = Mfl_kgpers * Cp_fluid_JperkgK * Nseg * (DELT * 3600) / (
                C_eff_Jperm2K * aperture_area_m2)
        if stability_criteria <= 0.5:
            print('ERROR: stability criteria', stability_criteria, 'is not reached.',
                  'aperture_area:', aperture_area_m2, 'mass flow:', Mfl_kgpers)
    return Mfl_kgpers


def update_negative_total_supply(aperture_area_m2, auxiliary_electricity_kW, flow, mcp_kWperK, pipe_lengths,
                                 specific_flows_kgpers, specific_pressure_losses_Pa, supply_losses_kW,
                                 supply_out_total_kW):
    """
    This function update the hot water production when losses are too high.
    When supply losses are higher than supply out (supply_out_total <0), the hot water is re-circulated back to
    panels instead of sending it to down-stream equipment (DH or absorption chiller)
    :param aperture_area_m2: aperture area per panel
    :param auxiliary_electricity_kW: electricity required to pump hot water in the transmission pipelines
    :param flow: index for the iteration number
    :param mcp_kWperK:
    :param pipe_lengths: lengths of transmission pipes
    :param specific_flows_kgpers: specific mass flow of hot water in panels
    :param specific_pressure_losses_Pa: specific pressure drop per panel
    :param supply_losses_kW: heat loss through transmission pipelines
    :param supply_out_total_kW: total heat supply
    :return:
    """
    # when losses are too high, re-circulate the hot water back to panels instead of sending it out
    if supply_out_total_kW.min() < 0:
        index_negative_supply_list = np.where(supply_out_total_kW < 0)[0].tolist()
        for i in index_negative_supply_list:
            # zero flow is sent to down-stream equipment (DH or absorption chiller)
            supply_out_total_kW[i] = 0
            supply_losses_kW[flow][i] = 0
            mcp_kWperK[i] = 0
            if supply_out_total_kW[i + 1] <= 0:
                # turn off the collector if no heat is produced in the following time-steps
                auxiliary_electricity_kW[flow][i] = 0
            else:
                # calculate electricity required to re-circulate hot water back to panels
                auxiliary_electricity_kW[flow][i] = calc_Eaux_panels(specific_flows_kgpers[flow][i],
                                                                     specific_pressure_losses_Pa[flow][i],
                                                                     pipe_lengths, aperture_area_m2)


@jit(nopython=True)
def calc_q_rad(n0, IAM_b, IAM_d, I_direct_Wperm2, I_diffuse_Wperm2, tilt):
    """
    Calculates the absorbed radiation for solar thermal collectors.
    :param n0: zero loss efficiency [-]
    :param IAM_b: incidence angle modifier for beam radiation [-]
    :param I_direct: direct/beam radiation [W/m2]
    :param IAM_d: incidence angle modifier for diffuse radiation [-]
    :param I_diffuse: diffuse radiation [W/m2]
    :param tilt: solar panel tilt angle [rad]
    :return q_rad: absorbed radiation [W/m2]
    """

    q_rad_Wperm2 = n0 * IAM_b * I_direct_Wperm2 + n0 * IAM_d * I_diffuse_Wperm2 * (1 + cos(tilt)) / 2
    return q_rad_Wperm2


@jit(nopython=True)
def calc_q_gain(Tfl, q_rad_Whperm2, DT, Tin, aperture_area_m2, c1, c2, Mfl, delts, Cp_waterglycol, C_eff,
                Te):
    """
    calculate the collector heat gain through iteration including temperature dependent thermal losses of the collectors.
    :param Tfl: mean fluid temperature
    :param q_rad_Whperm2: absorbed radiation per aperture [Wh/m2]
    :param DT: temperature differences between collector and ambient [K]
    :param Tin: collector inlet temperature [K]
    :param aperture_area_m2: aperture area [m2]
    :param c1: collector heat loss coefficient at zero temperature difference and wind speed [W/m2K]
    :param c2: temperature difference dependency of the heat loss coefficient [W/m2K2]
    :param Mfl: mass flow rate [kg/s]
    :param delts:
    :param Cp_waterglycol: heat capacity of water glycol [J/kgK]
    :param C_eff: thermal capacitance of module [J/m2K]
    :param Te: ambient temperature
    :return:
    ..[M. Haller et al., 2012] Haller, M., Perers, B., Bale, C., Paavilainen, J., Dalibard, A. Fischer, S. & Bertram, E.
    (2012). TRNSYS Type 832 v5.00 " Dynamic Collector Model by Bengt Perers". Updated Input-Output Reference.
    """

    xgain = 1
    xgainmax = 100
    exit = False
    while not exit:
        qgain_Whperm2 = q_rad_Whperm2 - c1 * (DT[1]) - c2 * abs(DT[1]) * DT[1]  # heat production from collector, eq.(5)

        if Mfl > 0:
            Tout = ((Mfl * Cp_waterglycol * Tin) / aperture_area_m2 - (C_eff * Tin) / (2 * delts) + qgain_Whperm2 + (
                    C_eff * Tfl[1]) / delts) / (Mfl * Cp_waterglycol / aperture_area_m2 + C_eff / (2 * delts))  # eq.(6)
            Tfl[2] = (Tin + Tout) / 2
            DT[2] = Tfl[2] - Te
            qdiff = Mfl / aperture_area_m2 * Cp_waterglycol * 2 * (DT[2] - DT[1])
        else:
            Tout = Tfl[1] + (qgain_Whperm2 * delts) / C_eff  # eq.(8)
            Tfl[2] = Tout
            DT[2] = Tfl[2] - Te
            qdiff = 5 * (DT[2] - DT[1])

        if abs(qdiff < 0.1):
            DT[1] = DT[2]
            exit = True
        else:
            if xgain > 40:
                DT[1] = (DT[1] + DT[2]) / 2
                if xgain == xgainmax:
                    exit = True
            else:
                DT[1] = DT[2]
        xgain += 1

    return qgain_Whperm2


def calc_qloss_network(Mfl, Le, Area_a, Tm, Te, maxmsc):
    """
    calculate non-recoverable losses
    :param Mfl: mass flow rate [kg/s]
    :param Le: length per aperture area [m/m2 aperture]
    :param Area_a: aperture area [m2]
    :param Tm: mean temperature
    :param Te: ambient temperature
    :param maxmsc: maximum mass flow [kg/s]
    :return:
    ..[ J. Fonseca et al., 2016] Fonseca, J., Nguyen, T-A., Schlueter, A., Marechal, F. City Energy Analyst:
    Integrated framework for analysis and optimization of building energy systems in neighborhoods and city districts.
    Energy and Buildings, 2016.
    ..
    """

    qloss_kW = constants.k_msc_max_WpermK * Le * Area_a * (Tm - Te) * (
            Mfl / maxmsc) / 1000  # eq. (61) non-recoverable losses

    return qloss_kW  # in kW


def calc_IAM_beam_SC(solar_properties, teta_z_deg, tilt_angle_deg, type_SCpanel, latitude_deg):
    """
    To calculate Incidence angle modifier for beam radiation.
    :param solar_properties: solar properties
    :type solar_properties: dataframe
    :param teta_z_deg: panel surface azimuth angle [rad]
    :type teta_z_deg: float
    :param tilt_angle_deg: panel tilt angle
    :type tilt_angle_deg: float
    :param type_SCpanel: type of SC
    :type type_SCpanel: unicode
    :param latitude_deg: latitude of the case study site
    :type latitude_deg: float
    :return:
    """

    def calc_teta_L(Az, teta_z, tilt, Sz):
        teta_la = tan(Sz) * cos(teta_z - Az)
        teta_l_deg = degrees(abs(atan(teta_la) - tilt))
        if teta_l_deg < 0:
            teta_l_deg = min(89, abs(teta_l_deg))
        if teta_l_deg >= 90:
            teta_l_deg = 89.999
        return teta_l_deg  # longitudinal incidence angle in degrees

    def calc_teta_T(Az, Sz, teta_z):
        teta_ta = sin(Sz) * sin(abs(teta_z - Az))
        teta_T_deg = degrees(atan(teta_ta / cos(teta_ta)))
        if teta_T_deg < 0:
            teta_T_deg = min(89, abs(teta_T_deg))
        if teta_T_deg >= 90:
            teta_T_deg = 89.999
        return teta_T_deg  # transversal incidence angle in degrees

    def calc_teta_L_max(teta_L_deg):
        if teta_L_deg < 0:
            teta_L_deg = min(89, abs(teta_L_deg))
        if teta_L_deg >= 90:
            teta_L_deg = 89.999
        return teta_L_deg

    def calc_IAMb(teta_l, teta_T, type_SCpanel):
        if type_SCpanel == 'FP':  # # Flat plate collector   1636: SOLEX BLU, SPF, 2012
            IAM_b = -0.00000002127039627042 * teta_l ** 4 + 0.00000143550893550934 * teta_l ** 3 - 0.00008493589743580050 * teta_l ** 2 + 0.00041588966590833100 * teta_l + 0.99930069929920900000
        if type_SCpanel == 'ET':  # # evacuated tube   Zewotherm ZEWO-SOL ZX 30, SPF, 2012
            IAML = -0.00000003365384615386 * teta_l ** 4 + 0.00000268745143745027 * teta_l ** 3 - 0.00010196678321666700 * teta_l ** 2 + 0.00088830613832779900 * teta_l + 0.99793706293541500000
            IAMT = 0.000000002794872 * teta_T ** 5 - 0.000000534731935 * teta_T ** 4 + 0.000027381118880 * teta_T ** 3 - 0.000326340326281 * teta_T ** 2 + 0.002973799531468 * teta_T + 1.000713286764210
            IAM_b = IAMT * IAML  # overall incidence angle modifier for beam radiation
        return IAM_b

    # Adjust sign convention: in Duffie (2013) collector azimuth facing equator = 0◦ (p. xxxiii)
    if latitude_deg >= 0:
        Az = solar_properties.Az - 180  # south is 0°, east is negative and west is positive (p. 13)
    else:
        Az = solar_properties.Az  # north is 0°

    # convert to radians
    Sz_rad = np.radians(solar_properties.Sz)  # solar zenith angle
    Az_rad = np.radians(Az)  # solar_properties.Az)  # solar azimuth angle [rad]
    teta_z_rad = radians(teta_z_deg)
    tilt_rad = radians(tilt_angle_deg)

    incidence_angle_deg = pvlib.irradiance.aoi(tilt_angle_deg, teta_z_deg, solar_properties.Sz, Az)
    incidence_angle_rad = [radians(x) for x in incidence_angle_deg]  # incident angle in radians

    # calculate incident angles
    if type_SCpanel == 'FP':
        incident_angle_deg = np.degrees(incidence_angle_rad)
        teta_L_deg = np.vectorize(calc_teta_L_max)(incident_angle_deg)
        teta_T_deg = 0  # not necessary for flat plate collectors
    if type_SCpanel == 'ET':
        teta_L_deg = np.vectorize(calc_teta_L)(Az_rad, teta_z_rad, tilt_rad, Sz_rad)  # in degrees
        teta_T_deg = np.vectorize(calc_teta_T)(Az_rad, Sz_rad, teta_z_rad)  # in degrees

    # calculate incident angle modifier for beam radiation
    IAM_b_vector = np.vectorize(calc_IAMb)(teta_L_deg, teta_T_deg, type_SCpanel)

    return IAM_b_vector


def calc_properties_SC_db(database_path, config):
    """
    To assign SC module properties according to panel types.
    :param type_SCpanel: type of SC panel used
    :type type_SCpanel: string
    :return: dict with Properties of the panel taken form the database
    """
    if config.solar.type_SCpanel == 'FP':
        type_SCpanel = 'SC1'
    elif config.solar.type_SCpanel == 'ET':
        type_SCpanel = 'SC2'
    else:
        raise ValueError('this panel type ', config.solar.type_SCpanel, 'is not in the database!')
    data = pd.read_excel(database_path, sheet_name="SOLAR_THERMAL_PANELS")
    panel_properties = data[data['code'] == type_SCpanel].reset_index().T.to_dict()[0]

    return panel_properties


def vectorize_calc_Eaux_SC(scpecific_flow_kgpers, dP_collector_Pa, pipe_lengths, Aa_m2):
    Leq_mperm2 = pipe_lengths['Leq_mperm2']
    l_int_mperm2 = pipe_lengths['l_int_mperm2']
    return np.vectorize(calc_Eaux_SC)(scpecific_flow_kgpers, dP_collector_Pa, Leq_mperm2, l_int_mperm2, Aa_m2)


def calc_Eaux_SC(specific_flow_kgpers, dP_collector_Pa, Leq_mperm2, l_int_mperm2, Aa_m2):
    """
    Calculate auxiliary electricity for pumping heat transfer fluid through solar collectors to downstream equipment
    (absorption chiller, district heating network...).
    This include pressure losses from pipe friction, collector, and the building head.
    :param specific_flow_kgpers: mass flow [kg/s]
    :param dP_collector_Pa: pressure loss per module [Pa]
    :param Leq_mperm2: total pipe length per aperture area [m]
    :param Aa_m2: aperture area [m2]
    :return:
    """

    # read variables
    dpl_Paperm = constants.dpl_Paperm
    fcr = constants.fcr
    Ro_kgperm3 = constants.Ro_kgperm3
    eff_pumping = constants.eff_pumping

    # calculate pressure drops
    dP_friction_Pa = dpl_Paperm * Leq_mperm2 * Aa_m2 * fcr  # HANZENWILIAMSN PA
    dP_building_head_Pa = (l_int_mperm2 / 2) * Aa_m2 * Ro_kgperm3 * 9.8  # dP = H*rho*g, g = 9.8 m/s^2

    # calculate electricity requirement from pumps
    Eaux_kW = (specific_flow_kgpers / Ro_kgperm3) * (
            dP_collector_Pa + dP_friction_Pa + dP_building_head_Pa) / eff_pumping / 1000

    return Eaux_kW


def calc_Eaux_panels(specific_flow_kgpers, dP_collector_Pa, pipe_lengths, Aa_m2):
    """
    Calculate auxiliary electricity for pumping heat transfer fluid in solar collectors.
    This include pressure losses from pipe friction, collector.
    :param specific_flow_kgpers: mass flow [kg/s]
    :param dP_collector_Pa: pressure loss per module [Pa]
    :param Leq_mperm2: total pipe length per aperture area [m]
    :param Aa_m2: aperture area [m2]
    :return:
    """

    # read variables
    dpl_Paperm = constants.dpl_Paperm
    fcr = constants.fcr
    Ro_kgperm3 = constants.Ro_kgperm3
    eff_pumping = constants.eff_pumping
    Leq_mperm2 = pipe_lengths['Leq_mperm2']

    # calculate pressure drops
    dP_friction_Pa = dpl_Paperm * Leq_mperm2 * Aa_m2 * fcr  # HANZENWILIAMSN PA

    # calculate electricity requirement
    Eaux_kW = (specific_flow_kgpers / Ro_kgperm3) * (
            dP_collector_Pa + dP_friction_Pa) / eff_pumping / 1000  # kW from pumps

    return Eaux_kW  # energy spent in kW


def calc_optimal_mass_flow(q1, q2, q3, q4, E1, E2, E3, E4, m1, m2, m3, m4, dP1, dP2, dP3, dP4, Area_a):
    """
    This function determines the optimal mass flow rate and the corresponding pressure drop that maximize the
    total heat production in every time-step. It is done by maximizing the energy generation function (balance equation)
    assuming the electricity requirement is twice as valuable as the thermal output of the solar collector.
    :param q1: qout [kW] at zero flow rate
    :param q2: qout [kW] at nominal flow rate (mB0)
    :param q3: qout [kW] at maximum flow rate (mB_max)
    :param q4: qout [kW] at minimum flow rate (mB_min)
    :param E1: auxiliary electricity used at zero flow rate [kW]
    :param E2: auxiliary electricity used at nominal flow rate [kW]
    :param E3: auxiliary electricity used at max flow rate [kW]
    :param E4: auxiliary electricity used at min flow rate [kW]
    :param m1: zero flow rate [kg/hr/m2 aperture]
    :param m2: nominal flow rate (mB0) [kg/hr/m2 aperture]
    :param m3: maximum flow rate (mB_max) [kg/hr/m2 aperture]
    :param m4: minimum flow rate (mB_min) [kg/hr/m2 aperture]
    :param dP1: pressure drop [Pa/m2] at zero flow rate
    :param dP2: pressure drop [Pa/m2] at nominal flow rate (mB0)
    :param dP3: pressure drop [Pa/m2] at maximum flow rate (mB_max)
    :param dP4: pressure drop [Pa/m2] at minimum flow rate (mB_min)
    :param Area_a: aperture area [m2]
    :return mass_flow_opt: optimal mass flow at each hour [kg/s]
    :return dP_opt: pressure drop at optimal mass flow at each hour [Pa]
    ..[ J. Fonseca et al., 2016] Fonseca, J., Nguyen, T-A., Schlueter, A., Marechal, F. City Energy Analyst:
    Integrated framework for analysis and optimization of building energy systems in neighborhoods and city districts.
    Energy and Buildings, 2016.
    """

    mass_flow_opt = np.empty(HOURS_IN_YEAR)
    dP_opt = np.empty(HOURS_IN_YEAR)
    const = Area_a / 3600
    mass_flow_all_kgpers = [m1 * const, m2 * const, m3 * const, m4 * const]  # [kg/s]
    dP_all_Pa = [dP1 * Area_a, dP2 * Area_a, dP3 * Area_a, dP4 * Area_a]  # [Pa]
    balances = [abs(q1) - E1 * 2, q2 - E2 * 2, q3 - E3 * 2, q4 - E4 * 2]  # energy generation function eq.(63)
    for t in range(HOURS_IN_YEAR):
        balances_time = [balances[0][t], balances[1][t], balances[2][t], balances[3][t]]
        max_heat_production = np.max(balances_time)
        ix_max_heat_production = np.where(balances_time == max_heat_production)
        mass_flow_opt[t] = mass_flow_all_kgpers[ix_max_heat_production[0][0]]
        dP_opt[t] = dP_all_Pa[ix_max_heat_production[0][0]]
    return mass_flow_opt, dP_opt


def calc_optimal_mass_flow_2(m, q, dp):
    """
    Set mass flow and pressure drop to zero if the heat balance is negative.
    :param m: mass flow rate [kg/s]
    :param q: qout [kW]
    :param dp: pressure drop [Pa]
    :return m: hourly mass flow rate [kg/s]
    :return dp: hourly pressure drop [Pa]
    """
    for t in range(HOURS_IN_YEAR):
        if q[t] <= 0:
            m[t] = 0
            dp[t] = 0
    return m, dp


# investment and maintenance costs
def calc_Cinv_SC(Area_m2, locator, panel_type):
    """
    Lifetime 35 years
    """
    if Area_m2 > 0.0:
        SC_cost_data = pd.read_excel(locator.get_database_conversion_systems(), sheet_name="SOLAR_THERMAL_PANELS")
        SC_cost_data = SC_cost_data[SC_cost_data['type'] == panel_type]
        cap_min = SC_cost_data['cap_min'].values[0]
        cap_max = SC_cost_data['cap_max'].values[0]
        # if the Q_design is below the lowest capacity available for the technology, then it is replaced by the least
        # capacity for the corresponding technology from the database
        if Area_m2 <= cap_min:
            Area_m2 = cap_min
        Inv_a = SC_cost_data['a'].values[0]
        Inv_b = SC_cost_data['b'].values[0]
        Inv_c = SC_cost_data['c'].values[0]
        Inv_d = SC_cost_data['d'].values[0]
        Inv_e = SC_cost_data['e'].values[0]
        Inv_IR = SC_cost_data['IR_%'].values[0]
        Inv_LT = SC_cost_data['LT_yr'].values[0]
        Inv_OM = SC_cost_data['O&M_%'].values[0] / 100

        InvC = Inv_a + Inv_b * (Area_m2) ** Inv_c + (Inv_d + Inv_e * Area_m2) * log(Area_m2)

        Capex_a_SC_USD = calc_capex_annualized(InvC, Inv_IR, Inv_LT)
        Opex_fixed_SC_USD = InvC * Inv_OM
        Capex_SC_USD = InvC
    else:
        Capex_a_SC_USD = Opex_fixed_SC_USD = Capex_SC_USD = 0.0

    return Capex_a_SC_USD, Opex_fixed_SC_USD, Capex_SC_USD


def main(config):
    assert os.path.exists(config.scenario), 'Scenario not found: %s' % config.scenario
    locator = cea.inputlocator.InputLocator(scenario=config.scenario)

    print('Running solar-collector with scenario = %s' % config.scenario)
    print(
        'Running solar-collector with annual-radiation-threshold-kWh/m2.yr = %s' % config.solar.annual_radiation_threshold)
    print('Running solar-collector with panel-on-roof = %s' % config.solar.panel_on_roof)
    print('Running solar-collector with panel-on-wall = %s' % config.solar.panel_on_wall)
    print('Running solar-collector with solar-window-solstice = %s' % config.solar.solar_window_solstice)
    print('Running solar-collector with t-in-sc = %s' % config.solar.t_in_sc)
    print('Running solar-collector with type-scpanel = %s' % config.solar.type_scpanel)
    if config.solar.custom_tilt_angle:
        print('Running photovoltaic with custom-tilt-angle = %s and panel-tilt-angle = %s' %
              (config.solar.custom_tilt_angle, config.solar.panel_tilt_angle))
    else:
        print('Running photovoltaic with custom-tilt-angle = %s' % config.solar.custom_tilt_angle)
    print('Running photovoltaic with maximum roof-coverage = %s' % config.solar.max_roof_coverage)

    building_names = config.solar.buildings

    zone_geometry = gdf.from_file(locator.get_zone_geometry())
    latitude, longitude = get_lat_lon_projected_shapefile(zone_geometry)

    panel_properties = calc_properties_SC_db(locator.get_database_conversion_systems(), config)
    panel_type = panel_properties['type']

    # weather data
    weather_data = epwreader.epw_reader(locator.get_weather_file())
    date_local = solar_equations.calc_datetime_local_from_weather_file(weather_data, latitude, longitude)
    print('reading weather data done')

    n = len(building_names)
    cea.utilities.parallel.vectorize(calc_SC, config.get_number_of_processes())(repeat(locator, n),
                                                                                repeat(config, n),
                                                                                repeat(latitude, n),
                                                                                repeat(longitude, n),
                                                                                repeat(weather_data, n),
                                                                                repeat(date_local, n),
                                                                                building_names)

    # aggregate results from all buildings
    aggregated_annual_results = {}
    for i, building in enumerate(building_names):
        hourly_results_per_building = pd.read_csv(locator.SC_results(building, panel_type)).set_index('Date')
        if i == 0:
            aggregated_hourly_results_df = hourly_results_per_building
            temperature_sup = hourly_results_per_building['T_SC_sup_C'].mean()
        else:
            aggregated_hourly_results_df = aggregated_hourly_results_df + hourly_results_per_building

        annual_energy_production = hourly_results_per_building.filter(like='_kWh').sum()
        panel_area_per_building = hourly_results_per_building.filter(like='_m2').iloc[0]
        building_annual_results = pd.concat([annual_energy_production, panel_area_per_building])
        aggregated_annual_results[building] = building_annual_results

    # save hourly results
    aggregated_hourly_results_df = aggregated_hourly_results_df[aggregated_hourly_results_df.columns.drop(
        aggregated_hourly_results_df.filter(like='Tout', axis=1).columns)]  # drop columns with Tout
    # recalculate average temperature supply and return of all panels
    aggregated_hourly_results_df['T_SC_sup_C'] = np.where(aggregated_hourly_results_df['mcp_SC_kWperC'] != 0,
                                                          temperature_sup, np.nan)
    aggregated_hourly_results_df['T_SC_re_C'] = np.where(aggregated_hourly_results_df['mcp_SC_kWperC'] != 0,
                                                         aggregated_hourly_results_df['T_SC_sup_C'] +
                                                         aggregated_hourly_results_df['Q_SC_gen_kWh'] /
                                                         aggregated_hourly_results_df['mcp_SC_kWperC'],
                                                         np.nan)
    aggregated_hourly_results_df.to_csv(locator.SC_totals(panel_type), index=True, float_format='%.2f', na_rep='nan')
    # save annual results
    aggregated_annual_results_df = pd.DataFrame(aggregated_annual_results).T
    aggregated_annual_results_df.to_csv(locator.SC_total_buildings(panel_type), index=True, index_label="Name",
                                        float_format='%.2f', na_rep="nan")


if __name__ == '__main__':
    t0 = time.perf_counter()
    main(cea.config.Configuration())
    print('Total time elapsed: %f seconds' % (time.perf_counter() - t0))
