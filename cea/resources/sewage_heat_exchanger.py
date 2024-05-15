# -*- coding: utf-8 -*-
"""
Sewage source heat exchanger
"""



import pandas as pd
import numpy as np
import scipy
import math
from cea.constants import HEX_WIDTH_M,VEL_FLOW_MPERS, HEAT_CAPACITY_OF_WATER_JPERKGK, H0_KWPERM2K, MIN_FLOW_LPERS, T_MIN, AT_MIN_K, P_SEWAGEWATER_KGPERM3, MULTI_RES_OCC
import cea.config
import cea.inputlocator
from cea.datamanagement.surroundings_helper import get_surrounding_building_sewage

__author__ = "Giuseppe Nappi"
__copyright__ = "Copyright 2015, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Jimeno A. Fonseca"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Daren Thomas"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"


def calc_sewage_heat_exchanger(locator, config):
    """
    Calculate the heat extracted from the sewage HEX.

    :param locator: an InputLocator instance set to the scenario to work on
    :param Length_HEX_available: HEX length available
    :type Length_HEX_available: float

    Save the results to `SWP.csv`
    """

    # local variables
    mcpwaste = []
    twaste = []
    mXt = []
    counter = 0

    # Configuration variables
    names = pd.read_csv(locator.get_total_demand()).Name
    sewage_water_ratio = config.sewage.sewage_water_ratio
    heat_exchanger_length = config.sewage.heat_exchanger_length
    freshwater_temperature = config.sewage.fresh_water_temperature
    ground_temperature = config.sewage.ground_temperature
    water_consumption = config.sewage.water_consumption_person
    sewage_temperature_drop = config.sewage.sewage_temperature_drop
    max_temperature = config.sewage.maximum_temperature_increase

    surroundings_sewage, buffer_m = get_surrounding_building_sewage(locator)
    T_sewage_drop = buffer_m / 1000 * sewage_temperature_drop
    V_lps_external = calculate_external_sewage_flow(surroundings_sewage, locator, water_consumption)

    for building_name in names:
        building = pd.read_csv(locator.get_demand_results_file(building_name))
        mcp_combi, t_to_sewage = np.vectorize(calc_Sewagetemperature)(building.Qww_sys_kWh, building.Qww_kWh, building.Tww_sys_sup_C,
                                                     building.Tww_sys_re_C, building.mcptw_kWperC, building.mcpww_sys_kWperC, sewage_water_ratio, freshwater_temperature)
        mcpwaste.append(mcp_combi)
        twaste.append(t_to_sewage)
        mXt.append(mcp_combi*t_to_sewage)
        counter = counter +1
    mcpwaste_zone = np.sum(mcpwaste, axis =0)
    mXt_zone = np.sum(mXt, axis =0)
    twaste_zone = [x * (y**-1) * 0.8 if y != 0 else 0 for x,y in zip (mXt_zone, mcpwaste_zone)] # losses in the grid of 20%

    Q_source, t_source, t_in_sew, t_out, tin_e, tout_e, mcpwaste_total = np.vectorize(calc_sewageheat)(mcpwaste_zone, twaste_zone, HEX_WIDTH_M,
                                                                              VEL_FLOW_MPERS, H0_KWPERM2K, MIN_FLOW_LPERS,
                                                                              heat_exchanger_length, T_MIN, AT_MIN_K, V_lps_external, T_sewage_drop, ground_temperature, max_temperature)

    #save to disk
    pd.DataFrame({"Qsw_kW" : Q_source, "Ts_C" : t_source, "T_out_sw_C" : t_out, "T_in_sw_C" : t_in_sew,
                  "mww_zone_kWperC":mcpwaste_total,
                    "T_out_HP_C" : tout_e, "T_in_HP_C" : tin_e}).to_csv(locator.get_sewage_heat_potential(),
                                                                      index=False, float_format='%.3f')
    avg_temp = np.mean(t_in_sew)
    return avg_temp




# Calc Sewage heat

def calc_Sewagetemperature(Qwwf, Qww, tsww, trww, mcptw, mcpww, SW_ratio, freshwater_temperature):
    """
    Calculate sewage temperature and flow rate released from DHW usages and Fresh Water (FW) in buildings.

    :param Qwwf: final DHW heat requirement
    :type Qwwf: float
    :param Qww: DHW heat requirement
    :type Qww: float
    :param tsww: DHW supply temperature
    :type tsww: float
    :param trww: DHW return temperature
    :type trww: float
    :param mcptw: fresh water flow rate
    :type mcptw: float
    :param mcpww: DHW heat capacity
    :type mcpww: float
    :param SW_ratio: ratio of decrease/increase in sewage water due to solids and also water intakes.
    :type SW_ratio: float

    :returns mcp_combi: sewage water heat capacity [kW_K]
    :rtype mcp_combi: float
    :returns t_to_sewage: sewage water temperature
    :rtype t_to_sewage: float
    """

    if Qwwf > 0:
        Qloss_to_spur = Qwwf - Qww
        t_spur = tsww - Qloss_to_spur / mcpww
        m_DHW = mcpww * SW_ratio
        m_TW = mcptw * SW_ratio
        mcp_combi = m_DHW + m_TW
        t_combi = ( m_DHW * t_spur + m_TW * freshwater_temperature ) / mcp_combi
        t_to_sewage = 0.90 * t_combi                  # assuming 10% thermal loss through piping
    else:
        t_to_sewage = trww
        mcp_combi = mcptw * SW_ratio  # in [kW_K]
    return mcp_combi, t_to_sewage # in lh or kgh and in C

def calc_sewageheat(mcp_kWC_zone, tin_C, w_HEX_m, Vf_ms, h0, min_lps, L_HEX_m, tmin_C, ATmin, V_lps_external, T_sewage_drop, ground_temperature, max_temperature):
    """
    Calculates the operation of sewage heat exchanger.

    :param mcp_kWC_total: heat capacity of total sewage in a zone
    :type mcp_kWC_total: float
    :param tin_C: sewage inlet temperature of a zone
    :type tin_C: float
    :param w_HEX_m: width of the sewage HEX
    :type w_HEX_m: float
    :param Vf_ms: sewage flow rate [m/s]
    :type Vf_ms: float
    :param cp: water specific heat capacity
    :type cp: float
    :param h0: sewage heat transfer coefficient
    :type h0: float
    :param min_lps: sewage minimum flow rate in [lps]
    :type min_lps: float
    :param L_HEX_m: HEX length available
    :type L_HEX_m: float
    :param tmin_C: minimum temperature of extraction
    :type tmin_C: float
    :param ATmin: minimum area of heat exchange
    :type ATmin: float

    :returns Q_source: heat supplied by sewage
    :rtype: float
    :returns t_source: sewage heat supply temperature
    :rtype t_source: float
    :returns tb2: sewage return temperature
    :rtype tbs: float
    :returns ta1: temperature inlet of the cold stream (from the HP)
    :rtype ta1: float
    :returns ta2: temperature outlet of the cold stream (to the HP)
    :rtype ta2: float

    ..[J.A. Fonseca et al., 2016] J.A. Fonseca, Thuy-An Nguyen, Arno Schlueter, Francois Marechal (2016). City Enegy
    Analyst (CEA): Integrated framework for analysis and optimization of building energy systems in neighborhoods and
    city districts. Energy and Buildings.
    """
    V_lps_zone = mcp_kWC_zone/ (HEAT_CAPACITY_OF_WATER_JPERKGK / 1E3)
    V_lps_total = V_lps_zone + V_lps_external
    mcp_kWC_external = (V_lps_external /1000) * P_SEWAGEWATER_KGPERM3 * (HEAT_CAPACITY_OF_WATER_JPERKGK/1E3)  # kW_C
    mcp_kWC_total = mcp_kWC_zone + mcp_kWC_external  # kW_C

    t_sewage_external = tin_C - T_sewage_drop  # °C
    if t_sewage_external < ground_temperature:
        t_sewage_external = ground_temperature

    if mcp_kWC_total != 0:
         t_sewage = (mcp_kWC_zone * tin_C + mcp_kWC_external * t_sewage_external) / mcp_kWC_total
    else:
         t_sewage = 0

    mcp_max = (Vf_ms * w_HEX_m * 0.20) * P_SEWAGEWATER_KGPERM3 * (HEAT_CAPACITY_OF_WATER_JPERKGK /1E3)  # 20 cm is the depth of the active water in contact with the HEX
    A_HEX = w_HEX_m * L_HEX_m   # area of heat exchange

    if min_lps < V_lps_total:
        if mcp_kWC_total >= mcp_max:
            mcp_kWC_total = mcp_max

        # B is the sewage, A is the heat pump
        mcpa = mcp_kWC_total * 1.1 # the flow in the heat pumps slightly above the flow on the sewage side
        tb1 = t_sewage
        ta1 = t_sewage - ((t_sewage - tmin_C) + ATmin / 2)
        alpha = h0 * A_HEX * (1 / mcpa - 1 / mcp_kWC_total)
        n = ( 1 - np.exp( -alpha ) ) / (1 - mcpa / mcp_kWC_total * np.exp(-alpha))
        tb2 = tb1 + mcpa / mcp_kWC_total * n * (ta1 - tb1)
        if mcp_kWC_total != 0:
            Q_source = mcp_kWC_total * (max_temperature - tb1)
        else:
            Q_source = 0
        ta2 = ta1 + Q_source / mcpa
        t_source = ( tb2 + tb1 ) / 2
    else:
        tb1 = t_sewage
        tb2 = t_sewage
        ta1 = t_sewage
        ta2 = t_sewage
        Q_source = 0
        t_source = t_sewage

    return Q_source, t_source, tb1, tb2, ta1, ta2, mcp_kWC_total

def calculate_external_sewage_flow(buffer_buildings, locator, water_consumption):
    """
    This function calculates the sewage water flow rate from the buildings in the surroundings of the zone.
    The sewage water flow rate is calculated based on the daily water consumption per person in Singapore, considering
    only residential buildings.
    """
    selected_buildings = filter_buildings(buffer_buildings, locator)

    # Extract the number of floors of the buildings
    list_floors_nr = selected_buildings['building:levels'].values
    floor_nr = []
    for item in list_floors_nr:
        x = float(item)

        if not math.isnan(x):
            floor_nr.append(int(x))
        else:
            floor_nr.append(1)

    # Extract the area of the buildings
    buildings_area = selected_buildings.area

    # Calculate the total area of the buildings included in the buffer and calculate nr of people
    tot_people = sum(buildings_area * floor_nr / selected_buildings.occupancy.values)
    water_consumption = tot_people * water_consumption / (3600 * 24)  # L/s

    return water_consumption

def update_ec(locator, sewage_temperature):
    water_temp = math.trunc(sewage_temperature)
    e_carriers = pd.read_excel(locator.get_database_energy_carriers(), sheet_name='ENERGY_CARRIERS')
    row_copy = e_carriers.loc[e_carriers['description'] == 'Fresh water'].copy()
    row_copy['mean_qual'] = water_temp
    row_copy['code'] = f'T{water_temp}SW'
    row_copy['description'] = 'Sewage Water'
    row_copy['subtype'] = 'water sink'

    if not e_carriers.loc[e_carriers['description'] == 'Sewage Water'].empty:
        row_copy.index = e_carriers.loc[e_carriers['description'] == 'Sewage Water'].index
        e_carriers.loc[e_carriers['description'] == 'Sewage Water'] = row_copy.copy()
    else:
        e_carriers = pd.concat([e_carriers, row_copy], axis=0)

    e_carriers.to_excel(locator.get_database_energy_carriers(), sheet_name='ENERGY_CARRIERS', index=False)

def filter_buildings(buffer_buildings, locator):
    
    ''' 
    This function calls the energy carrier database and adds the new energy carrier based on the temperature calculated.
    In this way, a different lake analysis can easily be updated.
    '''

    # Include buildings with large water consumption only
    included_buildings = {'residential': 'MULTI_RES', 'industrial': 'INDUSTRIAL', 'house': 'SINGLE_RES',
                          'apartment': 'MULTI_RES', 'hospital': 'HOSPITAL', 'hotel': 'HOTEL'}
    selected_buildings = buffer_buildings[buffer_buildings['building'].isin(included_buildings.keys())]
    typology_information = pd.read_excel(locator.get_database_use_types_properties(),'INTERNAL_LOADS')
    types = typology_information.set_index(typology_information['code'])

    for index, row in selected_buildings.iterrows():
        selected_buildings.loc[index, 'occupancy'] = types.loc[included_buildings[row['building']], 'Occ_m2p']

    return selected_buildings


def main(config):

    locator = cea.inputlocator.InputLocator(config.scenario)
    avg_temp = calc_sewage_heat_exchanger(locator=locator, config=config)
    update_ec(locator, avg_temp)


if __name__ == '__main__':
    main(cea.config.Configuration())