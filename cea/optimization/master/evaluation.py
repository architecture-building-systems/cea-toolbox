"""
Evaluation function of an individual

"""
from __future__ import division

import os

import numpy as np
import pandas as pd

from cea.constants import HOURS_IN_YEAR
from cea.optimization import slave_data
from cea.optimization import supportFn
from cea.optimization.constants import *
from cea.optimization.master import cost_model
from cea.optimization.master import summarize_network
from cea.optimization.master.performance_aggregation import summarize_results_individual
from cea.optimization.slave import cooling_main
from cea.optimization.slave import electricity_main
from cea.optimization.slave import heating_main
from cea.optimization.slave import natural_gas_main
from cea.optimization.slave.seasonal_storage import storage_main
from cea.resources.geothermal import calc_ground_temperature
from cea.technologies import substation
from cea.utilities import epwreader
from cea.optimization.master.generation import individual_to_barcode


# +++++++++++++++++++++++++++++++++++++
# Main objective function evaluation
# ++++++++++++++++++++++++++++++++++++++

def evaluation_main(individual, building_names, locator, network_features, config, prices, lca,
                    ind_num, gen, column_names, column_names_buildings_heating, column_names_buildings_cooling):
    """
    This function evaluates an individual

    :param individual: list with values of the individual
    :param building_names: list with names of buildings
    :param locator: locator class
    :param solar_features: solar features call to class
    :param network_features: network features call to class
    :param gv: global variables class
    :param optimization_constants: class containing constants used in optimization
    :param config: configuration file
    :param prices: class of prices used in optimization
    :type individual: list
    :type building_names: list
    :type locator: string
    :type solar_features: class
    :type network_features: class
    :type gv: class
    :type optimization_constants: class
    :type config: class
    :type prices: class
    :return: Resulting values of the objective function. costs, CO2, prim
    :rtype: tuple

    """

    # local variables
    district_heating_network = network_features.district_heating_network
    district_cooling_network = network_features.district_cooling_network
    num_total_buildings = len(building_names)
    solar_features = SolarFeatures()

    # CREATE THE INDIVIDUAL BARCODE AND INDIVIDUAL WITH HER COLUMN NAME AS A DICT
    DHN_barcode, DCN_barcode, individual_with_name_dict = individual_to_barcode(individual,
                                                                                column_names,
                                                                                column_names_buildings_heating,
                                                                                column_names_buildings_cooling)

    # CREATE CLASS AND PASS KEY CHARACTERISTICS OF INDIVIDUAL
    # THIS CLASS SHOULD CONTAIN ALL VARIABLES THAT MAKE AN INDIVIDUAL CONFIGURATION
    master_to_slave_vars = export_data_to_master_to_slave_class(locator, gen,
                                                                individual_with_name_dict,
                                                                ind_num, building_names,
                                                                num_total_buildings,
                                                                DHN_barcode, DCN_barcode, config,
                                                                district_heating_network,
                                                                district_cooling_network)
    # INITIALIZE DICTS STORING PERFORMANCE DATA
    performance_heating = {}
    performance_cooling = {}
    performance_storage = {}
    storage_dispatch = {}
    heating_dispatch = {}
    cooling_dispatch = {}

    # DISTRICT HEATING NETWORK
    if master_to_slave_vars.DHN_exists:
        print("CALCULATING SOLAR POTENTIAL CENTRAL HEATING GRID")
        solar_features = calc_solar_features_individual(locator, building_names, DHN_barcode,
                                                        master_to_slave_vars, solar_features)

        # THERMAL STORAGE
        print("CALCULATING ECOLOGICAL COSTS OF SEASONAL STORAGE - DUE TO OPERATION (IF ANY)")
        performance_storage, storage_dispatch = storage_main.storage_optimization(locator,
                                                                                  master_to_slave_vars,
                                                                                  lca, prices,
                                                                                  config)

        print("CALCULATING PERFORMANCE OF HEATING NETWORK CONNECTED BUILDINGS")
        performance_heating, heating_dispatch = heating_main.heating_calculations_of_DH_buildings(locator,
                                                                                                  master_to_slave_vars,
                                                                                                  config, prices,
                                                                                                  lca,
                                                                                                  solar_features,
                                                                                                  network_features,
                                                                                                  storage_dispatch)

    # DISTRICT COOLING NETWORK:
    if master_to_slave_vars.DCN_exists:
        print("CALCULATING PERFORMANCE OF COOLING NETWORK CONNECTED BUILDINGS")
        reduced_timesteps_flag = False
        performance_cooling, cooling_dispatch = cooling_main.cooling_calculations_of_DC_buildings(locator,
                                                                                                  master_to_slave_vars,
                                                                                                  network_features,
                                                                                                  prices,
                                                                                                  lca,
                                                                                                  config,
                                                                                                  reduced_timesteps_flag,
                                                                                                  district_heating_network)

    # DISCONNECTED BUILDINGS
    print("CALCULATING PERFORMANCE OF DISCONNECTED BUILDNGS")
    performance_disconnected = cost_model.add_disconnected_costs(building_names, locator, master_to_slave_vars)

    # ELECTRICITY CONSUMPTION CALCULATIONS
    print("CALCULATING PERFORMANCE OF ELECTRICITY CONSUMPTION")
    performance_electricity, \
    electricity_dispatch, \
    performance_heating, \
    performance_cooling, = electricity_main.electricity_calculations_of_all_buildings(locator,
                                                                                      master_to_slave_vars,
                                                                                      lca,
                                                                                      solar_features,
                                                                                      performance_heating,
                                                                                      performance_cooling,
                                                                                      heating_dispatch,
                                                                                      cooling_dispatch)

    # NATURAL GAS
    print("CALCULATING PERFORMANCE OF NATURAL GAS CONSUMPTION")
    fuels_dispatch = natural_gas_main.fuel_imports(master_to_slave_vars, heating_dispatch,
                                                   cooling_dispatch)

    print("AGGREGATING RESULTS")
    TAC_sys_USD, GHG_sys_tonCO2, PEN_sys_MJoil, performance_totals = summarize_results_individual(master_to_slave_vars,
                                                                                                  performance_storage,
                                                                                                  performance_heating,
                                                                                                  performance_cooling,
                                                                                                  performance_disconnected,
                                                                                                  performance_electricity)

    print("SAVING RESULTS TO DISK")
    save_results(master_to_slave_vars, locator, performance_heating, performance_cooling, performance_electricity,
                 performance_disconnected, storage_dispatch, heating_dispatch, cooling_dispatch, electricity_dispatch,
                 fuels_dispatch, performance_totals)

    # Converting costs into float64 to avoid longer values
    print ('Total TAC in USD = ' + str(TAC_sys_USD))
    print ('Total GHG emissions in tonCO2-eq = ' + str(GHG_sys_tonCO2))
    print ('Total PEN non-renewable in MJoil ' + str(PEN_sys_MJoil) + "\n")

    return TAC_sys_USD, GHG_sys_tonCO2, PEN_sys_MJoil


def save_results(master_to_slave_vars, locator, performance_heating, performance_cooling, performance_electricity,
                 performance_disconnected, storage_dispatch, heating_dispatch, cooling_dispatch, electricity_dispatch,
                 fuels_dispatch, performance_totals):
    # put data inside a list, otherwise pandas cannot save it
    for column in performance_disconnected.keys():
        performance_disconnected[column] = [performance_disconnected[column]]
    for column in performance_cooling.keys():
        performance_cooling[column] = [performance_cooling[column]]
    for column in performance_heating.keys():
        performance_heating[column] = [performance_heating[column]]
    for column in performance_electricity.keys():
        performance_electricity[column] = [performance_electricity[column]]
    for column in performance_totals.keys():
        performance_totals[column] = [performance_totals[column]]

    # export all including performance heating and performance cooling since we changed them
    pd.DataFrame(performance_disconnected).to_csv(
        locator.get_optimization_slave_disconnected_performance(master_to_slave_vars.individual_number,
                                                                master_to_slave_vars.generation_number),
        index=False)

    pd.DataFrame(performance_cooling).to_csv(
        locator.get_optimization_slave_cooling_performance(master_to_slave_vars.individual_number,
                                                           master_to_slave_vars.generation_number),
        index=False)

    pd.DataFrame(performance_heating).to_csv(
        locator.get_optimization_slave_heating_performance(master_to_slave_vars.individual_number,
                                                           master_to_slave_vars.generation_number),
        index=False)

    pd.DataFrame(performance_electricity).to_csv(
        locator.get_optimization_slave_electricity_performance(master_to_slave_vars.individual_number,
                                                               master_to_slave_vars.generation_number),
        index=False)

    pd.DataFrame(performance_totals).to_csv(
        locator.get_optimization_slave_total_performance(master_to_slave_vars.individual_number,
                                                         master_to_slave_vars.generation_number),
        index=False)

    # add date and plot
    DATE = master_to_slave_vars.date
    storage_dispatch['DATE'] = DATE
    electricity_dispatch['DATE'] = DATE
    cooling_dispatch['DATE'] = DATE
    heating_dispatch['DATE'] = DATE
    fuels_dispatch['DATE'] = DATE
    pd.DataFrame(storage_dispatch).to_csv(locator.get_optimization_slave_storage_operation_data(
        master_to_slave_vars.individual_number,
        master_to_slave_vars.generation_number), index=False)

    pd.DataFrame(electricity_dispatch).to_csv(locator.get_optimization_slave_electricity_activation_pattern(
        master_to_slave_vars.individual_number, master_to_slave_vars.generation_number), index=False)

    pd.DataFrame(cooling_dispatch).to_csv(
        locator.get_optimization_slave_cooling_activation_pattern(master_to_slave_vars.individual_number,
                                                                  master_to_slave_vars.generation_number),
        index=False)

    pd.DataFrame(heating_dispatch).to_csv(
        locator.get_optimization_slave_heating_activation_pattern(master_to_slave_vars.individual_number,
                                                                  master_to_slave_vars.generation_number),
        index=False)

    pd.DataFrame(fuels_dispatch).to_csv(
        locator.get_optimization_slave_natural_gas_imports(master_to_slave_vars.individual_number,
                                                           master_to_slave_vars.generation_number), index=False)


class SolarFeatures(object):
    def __init__(self):
        # import and sum all the area available

        self.Peak_PV_Wh = 0.0
        self.A_PV_m2 = 0.0
        self.Peak_PVT_Wh = 0.0
        self.Q_nom_PVT_Wh = 0.0
        self.A_PVT_m2 = 0.0
        self.Q_nom_SC_FP_Wh = 0.0
        self.A_SC_FP_m2 = 0.0
        self.Q_nom_SC_ET_Wh = 0.0
        self.A_SC_ET_m2 = 0.0


def calc_solar_features_individual(locator, building_names, DHN_barcode, master_to_slave_vars,
                                   solar_features):
    E_PV_gen_kWh = np.zeros(HOURS_IN_YEAR)
    E_PVT_gen_kWh = np.zeros(HOURS_IN_YEAR)
    Q_PVT_gen_kWh = np.zeros(HOURS_IN_YEAR)
    Q_SC_FP_gen_kWh = np.zeros(HOURS_IN_YEAR)
    Q_SC_ET_gen_kWh = np.zeros(HOURS_IN_YEAR)
    A_PV_m2 = np.zeros(HOURS_IN_YEAR)
    A_PVT_m2 = np.zeros(HOURS_IN_YEAR)
    A_SC_FP_m2 = np.zeros(HOURS_IN_YEAR)
    A_SC_ET_m2 = np.zeros(HOURS_IN_YEAR)

    for index, name in zip(DHN_barcode, building_names):
        if index == "1":  # building is connected, then it has solar collectors
            if master_to_slave_vars.SOLAR_PART_PVT > 0.0E-3:  # if PVT
                building_PVT = pd.read_csv(os.path.join(locator.get_potentials_solar_folder(), name + '_PVT.csv'))
                E_PVT_gen_kWh += building_PVT['E_PVT_gen_kWh']
                Q_PVT_gen_kWh += building_PVT['Q_PVT_gen_kWh']
                A_PVT_m2 += building_PVT['Area_PVT_m2']
            if master_to_slave_vars.SOLAR_PART_SC_ET > 0.0E-3:  # if SC Evacuated tube
                building_SC_ET = pd.read_csv(os.path.join(locator.get_potentials_solar_folder(), name + '_SC_ET.csv'))
                Q_SC_ET_gen_kWh += building_SC_ET['Q_SC_gen_kWh']
                A_SC_ET_m2 += building_SC_ET['Area_SC_m2']
            if master_to_slave_vars.SOLAR_PART_SC_FP > 0.0E-3:  # if SC Flat Plate
                building_SC_FP = pd.read_csv(
                    os.path.join(locator.get_potentials_solar_folder(), name + '_SC_FP.csv'))
                Q_SC_FP_gen_kWh += building_SC_FP['Q_SC_gen_kWh']
                A_SC_FP_m2 += building_SC_FP['Area_SC_m2']

        # if PV accepted then get all the potential (all buildings can be ocnnected to the electrical grid
        if master_to_slave_vars.SOLAR_PART_PV > 0.0E-3:
            building_PV = pd.read_csv(os.path.join(locator.get_potentials_solar_folder(), name + '_PV.csv'))
            A_PV_m2 += building_PV['Area_PV_m2']
            E_PV_gen_kWh += E_PV_gen_kWh + building_PV['E_PV_gen_kWh']

    solar_features.Peak_PV_Wh = E_PV_gen_kWh.max() * 1E3
    solar_features.A_PV_m2 = A_PV_m2.max()
    solar_features.Peak_PVT_Wh = E_PVT_gen_kWh.max() * 1E3
    solar_features.Q_nom_PVT_Wh = Q_PVT_gen_kWh.max() * 1E3
    solar_features.A_PVT_m2 = A_PVT_m2.max()
    solar_features.Q_nom_SC_FP_Wh = Q_SC_FP_gen_kWh.max() * 1E3
    solar_features.A_SC_FP_m2 = A_SC_FP_m2.max()
    solar_features.Q_nom_SC_ET_Wh = Q_SC_ET_gen_kWh.max() * 1E3
    solar_features.A_SC_ET_m2 = A_SC_ET_m2.max()

    return solar_features


def export_data_to_master_to_slave_class(locator, gen,
                                         individual_with_name_dict,
                                         ind_num, building_names, num_total_buildings,
                                         DHN_barcode, DCN_barcode, config,
                                         district_heating_network,
                                         district_cooling_network
                                         ):
    # RECALCULATE THE NOMINAL LOADS FOR HEATING AND COOLING, INCL SOME NAMES OF FILES
    Q_cooling_nom_W, Q_heating_nom_W, \
    network_file_name_cooling, network_file_name_heating = extract_loads_individual(locator, individual_with_name_dict,
                                                                                    DCN_barcode,
                                                                                    DHN_barcode,
                                                                                    config,
                                                                                    num_total_buildings)

    # CREATE MASTER TO SLAVE AND FILL-IN
    master_to_slave_vars = calc_master_to_slave_variables(locator, gen,
                                                          ind_num,
                                                          individual_with_name_dict,
                                                          building_names,
                                                          num_total_buildings,
                                                          DHN_barcode,
                                                          DCN_barcode,
                                                          network_file_name_heating,
                                                          network_file_name_cooling,
                                                          Q_heating_nom_W,
                                                          Q_cooling_nom_W,
                                                          district_heating_network,
                                                          district_cooling_network
                                                          )

    return master_to_slave_vars


def extract_loads_individual(locator, individual_with_name_dict, DCN_barcode, DHN_barcode, config, num_total_buildings):
    # local variables
    weather_file = config.weather
    network_depth_m = Z0
    T_ambient = epwreader.epw_reader(weather_file)['drybulb_C']
    ground_temp = calc_ground_temperature(locator, T_ambient, depth_m=network_depth_m)

    # EVALUATE CASES TO CREATE A NETWORK OR NOT
    if DHN_barcode.count("1") == num_total_buildings:
        network_file_name_heating = "DH_Network_summary_result_all.csv"
        Q_DHNf_W = pd.read_csv(locator.get_optimization_network_all_results_summary('DH', 'all'),
                               usecols=["Q_DHNf_W"]).values
        Q_heating_max_W = Q_DHNf_W.max()
    elif DHN_barcode.count("1") == 0:  # no network at all
        network_file_name_heating = "DH_Network_summary_result_all.csv"
        Q_heating_max_W = 0
    else:
        network_file_name_heating = "DH_Network_summary_result_" + hex(int(str(DHN_barcode), 2)) + ".csv"
        if not os.path.exists(locator.get_optimization_network_results_summary('DH', DHN_barcode)):
            total_demand = supportFn.createTotalNtwCsv("DH", DHN_barcode, locator)
            buildings_in_heating_network = total_demand.Name.values
            # Run the substation and distribution routines
            substation.substation_main_heating(locator, total_demand, buildings_in_heating_network,
                                               DHN_barcode=DHN_barcode)
            summarize_network.network_main(locator, buildings_in_heating_network, ground_temp, num_total_buildings,
                                           "DH", DHN_barcode, DHN_barcode)

        Q_DHNf_W = pd.read_csv(locator.get_optimization_network_results_summary('DH', DHN_barcode),
                               usecols=["Q_DHNf_W"]).values
        Q_heating_max_W = Q_DHNf_W.max()

    if DCN_barcode.count("1") == num_total_buildings:
        network_file_name_cooling = "DC_Network_summary_result_all.csv"
        if individual_with_name_dict['HPServer'] == 1:
            # if heat recovery is ON, then only need to satisfy cooling load of space cooling and refrigeration
            Q_DCNf_W_no_data = pd.read_csv(locator.get_optimization_network_all_results_summary('DC', 'all'),
                                           usecols=["Q_DCNf_space_cooling_and_refrigeration_W"]).values
            Q_DCNf_W_with_data = pd.read_csv(locator.get_optimization_network_all_results_summary('DC', 'all'),
                                             usecols=["Q_DCNf_space_cooling_data_center_and_refrigeration_W"]).values

            Q_DCNf_W = Q_DCNf_W_no_data + (
                        (Q_DCNf_W_with_data - Q_DCNf_W_no_data) * (individual_with_name_dict['HPShare']))

        else:
            Q_DCNf_W = pd.read_csv(locator.get_optimization_network_all_results_summary('DC', 'all'),
                                   usecols=["Q_DCNf_space_cooling_data_center_and_refrigeration_W"]).values
        Q_cooling_max_W = Q_DCNf_W.max()
    elif DCN_barcode.count("1") == 0:
        network_file_name_cooling = "DC_Network_summary_result_all.csv"
        Q_cooling_max_W = 0.0
    else:
        network_file_name_cooling = "DC_Network_summary_result_" + hex(int(str(DCN_barcode), 2)) + ".csv"

        if not os.path.exists(locator.get_optimization_network_results_summary('DC', DCN_barcode)):
            total_demand = supportFn.createTotalNtwCsv("DC", DCN_barcode, locator)
            buildings_in_cooling_network = total_demand.Name.values

            # Run the substation and distribution routines
            substation.substation_main_cooling(locator, total_demand, buildings_in_cooling_network,
                                               DCN_barcode=DCN_barcode)
            summarize_network.network_main(locator, buildings_in_cooling_network, ground_temp, num_total_buildings,
                                           'DC', DCN_barcode, DCN_barcode)

        if individual_with_name_dict[
            'HPServer'] == 1:  # if heat recovery is ON, then only need to satisfy cooling load of space cooling and refrigeration
            Q_DCNf_W_no_data = pd.read_csv(locator.get_optimization_network_all_results_summary('DC', 'all'),
                                           usecols=["Q_DCNf_space_cooling_and_refrigeration_W"]).values
            Q_DCNf_W_with_data = pd.read_csv(locator.get_optimization_network_all_results_summary('DC', 'all'),
                                             usecols=["Q_DCNf_space_cooling_data_center_and_refrigeration_W"]).values

            Q_DCNf_W = Q_DCNf_W_no_data + (
                        (Q_DCNf_W_with_data - Q_DCNf_W_no_data) * (individual_with_name_dict['HPShare']))

        Q_cooling_max_W = Q_DCNf_W.max()

    Q_heating_nom_W = Q_heating_max_W * (1 + Q_MARGIN_FOR_NETWORK)
    Q_cooling_nom_W = Q_cooling_max_W * (1 + Q_MARGIN_FOR_NETWORK)

    return Q_cooling_nom_W, Q_heating_nom_W, network_file_name_cooling, network_file_name_heating


# +++++++++++++++++++++++++++++++++++
# Boundary conditions
# +++++++++++++++++++++++++++++
def calc_master_to_slave_variables(locator, gen,
                                   ind_num,
                                   individual_with_names_dict,
                                   building_names,
                                   num_total_buildings,
                                   DHN_barcode,
                                   DCN_barcode,
                                   network_file_name_heating,
                                   network_file_name_cooling,
                                   Q_heating_nom_W,
                                   Q_cooling_nom_W,
                                   district_heating_network,
                                   district_cooling_network
                                   ):
    """
    This function reads the list encoding a configuration and implements the corresponding
    for the slave routine's to use
    :param individual_with_names_dict: list with inidividual
    :param Q_heating_max_W:  peak heating demand
    :param locator: locator class
    :param gv: global variables class
    :type individual_with_names_dict: list
    :type Q_heating_max_W: float
    :type locator: string
    :type gv: class
    :return: master_to_slave_vars : class MasterSlaveVariables
    :rtype: class
    """

    # initialise class storing dynamic variables transfered from master to slave optimization
    master_to_slave_vars = slave_data.SlaveData()

    # Store information aobut individual regarding the configuration of the network and curstomers connected
    if district_heating_network and DHN_barcode.count("1") > 0:
        master_to_slave_vars.DHN_exists = True
    if district_cooling_network and DCN_barcode.count("1") > 0:
        master_to_slave_vars.DCN_exists = True
    master_to_slave_vars.number_of_buildings_connected_heating = DHN_barcode.count("1")
    master_to_slave_vars.number_of_buildings_connected_cooling = DCN_barcode.count("1")
    master_to_slave_vars.network_data_file_heating = network_file_name_heating
    master_to_slave_vars.network_data_file_cooling = network_file_name_cooling
    master_to_slave_vars.DHN_barcode = DHN_barcode
    master_to_slave_vars.DCN_barcode = DCN_barcode
    master_to_slave_vars.num_total_buildings = num_total_buildings
    master_to_slave_vars.building_names = building_names
    master_to_slave_vars.individual_with_names_dict = individual_with_names_dict

    # Store the number of the individual and the generation to which it belongs
    master_to_slave_vars.individual_number = ind_num
    master_to_slave_vars.generation_number = gen

    # Store useful variables to know where to save the results of the individual
    master_to_slave_vars.date = pd.read_csv(locator.get_demand_results_file(building_names[0])).DATE.values

    # Store inforamtion about which units are activated
    if master_to_slave_vars.DHN_exists:
        master_to_slave_vars = master_to_slace_DHN_variables(Q_heating_nom_W, individual_with_names_dict, locator, master_to_slave_vars)

    if master_to_slave_vars.DCN_exists:
        master_to_slave_vars = master_to_slave_DCN_variables(Q_cooling_nom_W, individual_with_names_dict, master_to_slave_vars)

    return master_to_slave_vars


def master_to_slave_DCN_variables(Q_cooling_nom_W, individual_with_names_dict, master_to_slave_vars):
    # COOLING SYSTEMS
    # Lake Cooling
    if individual_with_names_dict['FLake'] == 1 and LAKE_COOLING_ALLOWED is True:
        master_to_slave_vars.Lake_cooling_on = 1
        master_to_slave_vars.Lake_cooling_size_W = individual_with_names_dict['FLake Share'] * Q_cooling_nom_W
    # VCC Cooling
    if individual_with_names_dict['VCC'] == 1 and VCC_ALLOWED is True:
        master_to_slave_vars.VCC_on = 1
        master_to_slave_vars.VCC_cooling_size_W = individual_with_names_dict['VCC Share'] * Q_cooling_nom_W
    # Absorption Chiller Cooling
    if individual_with_names_dict['ACH'] == 1 and ABSORPTION_CHILLER_ALLOWED is True:
        master_to_slave_vars.Absorption_Chiller_on = 1
        master_to_slave_vars.Absorption_chiller_size_W = individual_with_names_dict['ACH Share'] * Q_cooling_nom_W
    # Storage Cooling
    if individual_with_names_dict['Storage'] == 1 and STORAGE_COOLING_ALLOWED is True:
        if (individual_with_names_dict['VCC'] == 1 and VCC_ALLOWED is True) or \
                (individual_with_names_dict['ACH'] == 1 and ABSORPTION_CHILLER_ALLOWED is True):
            master_to_slave_vars.storage_cooling_on = 1
            master_to_slave_vars.Storage_cooling_size_W = individual_with_names_dict['Storage Share'] * Q_cooling_nom_W
            if master_to_slave_vars.Storage_cooling_size_W > STORAGE_COOLING_SHARE_RESTRICTION * Q_cooling_nom_W:
                master_to_slave_vars.Storage_cooling_size_W = STORAGE_COOLING_SHARE_RESTRICTION * Q_cooling_nom_W

    return master_to_slave_vars


def master_to_slace_DHN_variables(Q_heating_nom_W, individual_with_names_dict, locator, master_to_slave_vars):

    if individual_with_names_dict['CHP/Furnace'] == 1 and FURNACE_ALLOWED == True:  # Wet-Biomass fired Furnace
        master_to_slave_vars.Furnace_on = 1
        master_to_slave_vars.Furnace_Q_max_W = individual_with_names_dict['CHP/Furnace Share'] * Q_heating_nom_W
        master_to_slave_vars.Furn_Moist_type = "wet"
    elif individual_with_names_dict['CHP/Furnace'] == 2 and CC_ALLOWED == True:  # NG-fired CHPFurnace
        master_to_slave_vars.CC_on = 1
        master_to_slave_vars.CC_GT_SIZE_W = individual_with_names_dict['CHP/Furnace Share'] * Q_heating_nom_W * 1.3
        # 1.3 is the conversion factor between the GT_Elec_size NG and Q_DHN
        master_to_slave_vars.gt_fuel = "NG"
    elif individual_with_names_dict['CHP/Furnace'] == 3 and FURNACE_ALLOWED == True:  # Dry-Biomass fired Furnace
        master_to_slave_vars.Furnace_on = 1
        master_to_slave_vars.Furnace_Q_max_W = individual_with_names_dict['CHP/Furnace Share'] * Q_heating_nom_W
        master_to_slave_vars.Furn_Moist_type = "dry"
    elif individual_with_names_dict['CHP/Furnace'] == 4 and CC_ALLOWED == True:  # Biogas-fired CHPFurnace
        master_to_slave_vars.CC_on = 1
        master_to_slave_vars.CC_GT_SIZE_W = individual_with_names_dict['CHP/Furnace Share'] * Q_heating_nom_W * 1.3
        # 1.3 is the conversion factor between the GT_Elec_size NG and Q_DHN
        master_to_slave_vars.gt_fuel = "BG"
    # Base boiler
    if individual_with_names_dict['BaseBoiler'] == 1:  # NG-fired boiler
        master_to_slave_vars.Boiler_on = 1
        master_to_slave_vars.Boiler_Q_max_W = individual_with_names_dict['BaseBoiler Share'] * Q_heating_nom_W
        master_to_slave_vars.BoilerType = "NG"
    elif individual_with_names_dict['BaseBoiler'] == 2:  # BG-fired boiler
        master_to_slave_vars.Boiler_on = 1
        master_to_slave_vars.Boiler_Q_max_W = individual_with_names_dict['BaseBoiler Share'] * Q_heating_nom_W
        master_to_slave_vars.BoilerType = "BG"
    # peak boiler
    if individual_with_names_dict['PeakBoiler'] == 1:  # BG-fired boiler
        master_to_slave_vars.BoilerPeak_on = 1
        master_to_slave_vars.BoilerPeak_Q_max_W = individual_with_names_dict['PeakBoiler Share'] * Q_heating_nom_W
        master_to_slave_vars.BoilerPeakType = "NG"
    if individual_with_names_dict['PeakBoiler'] == 2:  # BG-fired boiler
        master_to_slave_vars.BoilerPeak_on = 1
        master_to_slave_vars.BoilerPeak_Q_max_W = individual_with_names_dict['PeakBoiler Share'] * Q_heating_nom_W
        master_to_slave_vars.BoilerPeakType = "BG"
    # HPLake
    if individual_with_names_dict['HPLake'] == 1 and HP_LAKE_ALLOWED == True:
        lake_potential = pd.read_csv(locator.get_lake_potential())
        Q_max_lake = (lake_potential['QLake_kW'] * 1000).max()
        master_to_slave_vars.HP_Lake_on = 1
        master_to_slave_vars.HPLake_maxSize_W = min(individual_with_names_dict['HPLake Share'] * Q_max_lake,
                                                    individual_with_names_dict['HPLake Share'] * Q_heating_nom_W)
    # HPSewage
    if individual_with_names_dict['HPSewage'] == 1 and HP_SEW_ALLOWED == True:
        sewage_potential = pd.read_csv(locator.get_sewage_heat_potential())
        Q_max_sewage = (sewage_potential['Qsw_kW'] * 1000).max()
        master_to_slave_vars.HP_Sew_on = 1
        master_to_slave_vars.HPSew_maxSize_W = min(individual_with_names_dict['HPSewage Share'] * Q_max_sewage,
                                                   individual_with_names_dict['HPSewage Share'] * Q_heating_nom_W)
    # GHP
    if individual_with_names_dict['GHP'] == 1 and GHP_ALLOWED == True:
        ghp_potential = pd.read_csv(locator.get_geothermal_potential())
        Q_max_ghp = (ghp_potential['QGHP_kW'] * 1000).max()
        master_to_slave_vars.GHP_on = 1
        master_to_slave_vars.GHP_maxSize_W = min(individual_with_names_dict['GHP Share'] * Q_max_ghp,
                                                 individual_with_names_dict['GHP Share'] * Q_heating_nom_W)
    # HPServer
    if individual_with_names_dict['HPServer'] == 1 and DATACENTER_HEAT_RECOVERY_ALLOWED == True:
        master_to_slave_vars.WasteServersHeatRecovery = 1
        master_to_slave_vars.HPServer_maxSize_W = individual_with_names_dict['HPServer Share'] * Q_heating_nom_W
    # SOLAR TECHNOLOGIES
    master_to_slave_vars.SOLAR_PART_PV = individual_with_names_dict['PV Share']
    master_to_slave_vars.SOLAR_PART_PVT = individual_with_names_dict['PVT Share']
    master_to_slave_vars.SOLAR_PART_SC_ET = individual_with_names_dict['SC_ET Share']
    master_to_slave_vars.SOLAR_PART_SC_FP = individual_with_names_dict['SC_FP Share']

    return master_to_slave_vars


def epsIndicator(frontOld, frontNew):
    """
    This function computes the epsilon indicator
    
    :param frontOld: Old Pareto front
    :type frontOld: list
    :param frontNew: New Pareto front
    :type frontNew: list

    :return: epsilon indicator between the old and new Pareto fronts
    :rtype: float

    """
    epsInd = 0
    firstValueAll = True

    for indNew in frontNew:
        tempEpsInd = 0
        firstValue = True

        for indOld in frontOld:
            (aOld, bOld, cOld) = indOld.fitness.values
            (aNew, bNew, cNew) = indNew.fitness.values
            compare = max(aOld - aNew, bOld - bNew, cOld - cNew)

            if firstValue:
                tempEpsInd = compare
                firstValue = False

            if compare < tempEpsInd:
                tempEpsInd = compare

        if firstValueAll:
            epsInd = tempEpsInd
            firstValueAll = False

        if tempEpsInd > epsInd:
            epsInd = tempEpsInd

    return epsInd


