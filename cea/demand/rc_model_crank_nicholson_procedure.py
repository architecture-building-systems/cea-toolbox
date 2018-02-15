# -*- coding: utf-8 -*-


from __future__ import division
import warnings
import numpy as np
from cea.demand import airconditioning_model, rc_model_SIA, control_heating_cooling_systems, \
    space_emission_systems, latent_loads

__author__ = "Gabriel Happle"
__copyright__ = "Copyright 2016, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Gabriel Happle"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Daren Thomas"
__email__ = "thomas@arch.ethz.ch"
__status__ = "Production"


def calc_rc_model_demand_heating_cooling(bpr, tsd, t, gv):

    """
    Crank-Nicholson Procedure to calculate heating / cooling demand of buildings
    following the procedure in 2.3.2 in SIA 2044 / Korrigenda C1 zum Merkblatt SIA 2044:2011 / Korrigenda C2 zum Mekblatt SIA 2044:2011

    Special procedures for updating ventilation air AC-heated and AC-cooled buildings

    Author: Gabriel Happle
    Date: 01/2017

    :param bpr: building properties row object
    :param tsd: time series data dict
    :param t: time step / hour of year [0..8760]
    :param gv: globalvars
    :return: updates values in tsd
    """

    # following the procedure in 2.3.2 in SIA 2044 / Korrigenda C1 zum Merkblatt SIA 2044:2011
    #  / Korrigenda C2 zum Mekblatt SIA 2044:2011

    # ++++++++++++++++++++++++++++++
    # CASE 0 - NO HEATING OR COOLING
    # ++++++++++++++++++++++++++++++
    if not control_heating_cooling_systems.is_active_heating_system(bpr, tsd, t) \
            and not control_heating_cooling_systems.is_active_cooling_system(bpr, tsd, t):

        # STEP 1
        # ******
        # calculate temperatures
        rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_no_heating_cooling(bpr, tsd, t)

        # calculate humidity
        tsd['g_hu_ld'][t] = 0  # no humidification or dehumidification
        tsd['g_dhu_ld'][t] = 0
        latent_loads.calc_moisture_content_in_zone_local(bpr, tsd, t)

        # write to tsd
        tsd['T_int'][t] = rc_model_temperatures['T_int']
        tsd['theta_m'][t] = rc_model_temperatures['theta_m']
        tsd['theta_c'][t] = rc_model_temperatures['theta_c']
        tsd['theta_o'][t] = rc_model_temperatures['theta_o']
        update_tsd_no_cooling(tsd, t)
        update_tsd_no_heating(tsd, t)
        tsd['system_status'][t] = 'systems off'

    # ++++++++++++++++
    # CASE 1 - HEATING
    # ++++++++++++++++
    elif control_heating_cooling_systems.is_active_heating_system(bpr, tsd, t):
        # case for heating
        tsd['system_status'][t] = 'Radiative heating'

        # STEP 1
        # ******
        # calculate temperatures with 0 heating power
        rc_model_temperatures_0 = rc_model_SIA.calc_rc_model_temperatures_no_heating_cooling(bpr, tsd, t)

        T_int_0 = rc_model_temperatures_0['T_int']

        # STEP 2
        # ******
        # calculate temperatures with 10 W/m2 heating power
        phi_hc_10 = 10 * bpr.rc_model['Af']
        rc_model_temperatures_10 = rc_model_SIA.calc_rc_model_temperatures_heating(phi_hc_10, bpr, tsd, t)

        T_int_10 = rc_model_temperatures_10['T_int']

        T_int_set = tsd['ta_hs_set'][t]

        # interpolate heating power
        # (64) in SIA 2044 / Korrigenda C1 zum Merkblatt SIA 2044:2011 / Korrigenda C2 zum Mekblatt SIA 2044:2011
        phi_hc_ul = phi_hc_10*(T_int_set - T_int_0) / (T_int_10 - T_int_0)

        # STEP 3
        # ******
        # check if available power is sufficient
        phi_h_max = bpr.hvac['Qhsmax_Wm2'] * bpr.rc_model['Af']

        if 0 < phi_hc_ul <= phi_h_max:
            # case heating with phi_hc_ul
            # calculate temperatures with this power
            phi_h_act = phi_hc_ul

        elif 0 < phi_hc_ul > phi_h_max:
            # case heating with max power available
            # calculate temperatures with this power
            phi_h_act = phi_h_max
        else:
            raise Exception("something went wrong")

        # STEP 4
        # ******
        rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_heating(phi_h_act, bpr, tsd, t)
        # write necessary parameters for AC calculation to tsd
        tsd['T_int'][t] = rc_model_temperatures['T_int']
        tsd['theta_m'][t] = rc_model_temperatures['theta_m']
        tsd['theta_c'][t] = rc_model_temperatures['theta_c']
        tsd['theta_o'][t] = rc_model_temperatures['theta_o']
        tsd['Qhs_sen'][t] = phi_h_act
        tsd['Qhs_sen_sys'][t] = phi_h_act
        tsd['Qhs_lat_sys'][t] = 0
        tsd['Ehs_lat_aux'][t] = 0
        tsd['ma_sup_hs'][t] = 0
        tsd['Ta_sup_hs'][t] = 0
        tsd['Ta_re_hs'][t] = 0
        tsd['m_ve_recirculation'][t] = 0

        # STEP 5 - latent and sensible heat demand of AC systems
        # ******
        if control_heating_cooling_systems.heating_system_is_ac(bpr):
            air_con_model_loads_flows_temperatures = airconditioning_model.calc_hvac_heating(tsd, t)

            tsd['system_status'][t] = 'AC heating'

            # update temperatures for over heating case
            if air_con_model_loads_flows_temperatures['q_hs_sen_hvac'] > phi_h_act:
                phi_h_act_over_heating = air_con_model_loads_flows_temperatures['q_hs_sen_hvac']
                rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_heating(
                    phi_h_act_over_heating, bpr, tsd,
                    t)

                # update temperatures
                tsd['T_int'][t] = rc_model_temperatures['T_int']
                tsd['theta_m'][t] = rc_model_temperatures['theta_m']
                tsd['theta_c'][t] = rc_model_temperatures['theta_c']
                tsd['theta_o'][t] = rc_model_temperatures['theta_o']
                tsd['system_status'][t] = 'AC over heating'

            # update AC energy demand
            tsd['Qhs_sen_sys'][t] = air_con_model_loads_flows_temperatures['q_hs_sen_hvac']
            tsd['Qhs_lat_sys'][t] = air_con_model_loads_flows_temperatures['q_hs_lat_hvac']
            tsd['ma_sup_hs'][t] = air_con_model_loads_flows_temperatures['ma_sup_hs']
            tsd['Ta_sup_hs'][t] = air_con_model_loads_flows_temperatures['ta_sup_hs']
            tsd['Ta_re_hs'][t] = air_con_model_loads_flows_temperatures['ta_re_hs']
            tsd['Ehs_lat_aux'][t] = air_con_model_loads_flows_temperatures['e_hs_lat_aux']
            tsd['m_ve_recirculation'][t] = air_con_model_loads_flows_temperatures['m_ve_hvac_recirculation']

        # STEP 6 - emission system losses
        # ******
        q_em_ls_heating = space_emission_systems.calc_q_em_ls_heating(bpr, tsd, t)

        # set temperatures to tsd for heating
        tsd['T_int'][t] = rc_model_temperatures['T_int']
        tsd['theta_m'][t] = rc_model_temperatures['theta_m']
        tsd['theta_c'][t] = rc_model_temperatures['theta_c']
        tsd['theta_o'][t] = rc_model_temperatures['theta_o']
        tsd['Qhs_lat_sys'][t] = 0
        tsd['Qhs_em_ls'][t] = q_em_ls_heating
        tsd['Qhs_sen'][t] = phi_h_act
        tsd['Qhsf'][t] = 0
        tsd['Qhsf_lat'][t] = 0
        update_tsd_no_cooling(tsd, t)

    # ++++++++++++++++
    # CASE 2 - COOLING
    # ++++++++++++++++
    elif control_heating_cooling_systems.is_active_cooling_system(bpr, tsd, t):

        # case for cooling
        tsd['system_status'][t] = 'Radiative cooling'

        # STEP 1
        # ******
        # calculate temperatures with 0 heating power
        rc_model_temperatures_0 = rc_model_SIA.calc_rc_model_temperatures_no_heating_cooling(bpr, tsd, t)

        T_int_0 = rc_model_temperatures_0['T_int']

        # STEP 2
        # ******
        # calculate temperatures with 10 W/m2 cooling power
        phi_hc_10 = 10 * bpr.rc_model['Af']
        rc_model_temperatures_10 = rc_model_SIA.calc_rc_model_temperatures_cooling(phi_hc_10, bpr, tsd, t)

        T_int_10 = rc_model_temperatures_10['T_int']

        T_int_set = tsd['ta_cs_set'][t]

        # interpolate heating power
        # (64) in SIA 2044 / Korrigenda C1 zum Merkblatt SIA 2044:2011 / Korrigenda C2 zum Mekblatt SIA 2044:2011
        phi_hc_ul = phi_hc_10 * (T_int_set - T_int_0) / (T_int_10 - T_int_0)

        # STEP 3
        # ******
        # check if available power is sufficient
        phi_c_max = -bpr.hvac['Qcsmax_Wm2'] * bpr.rc_model['Af']

        if 0 > phi_hc_ul >= phi_c_max:
            # case heating with phi_hc_ul
            # calculate temperatures with this power
            phi_c_act = phi_hc_ul

        elif 0 > phi_hc_ul < phi_c_max:
            # case heating with max power available
            # calculate temperatures with this power
            phi_c_act = phi_c_max

        else:
            raise Exception("ups something went wrong")

        # STEP 4
        # ******
        rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_cooling(phi_c_act, bpr, tsd, t)

        # write necessary parameters for AC calculation to tsd
        tsd['T_int'][t] = rc_model_temperatures['T_int']
        tsd['theta_m'][t] = rc_model_temperatures['theta_m']
        tsd['theta_c'][t] = rc_model_temperatures['theta_c']
        tsd['theta_o'][t] = rc_model_temperatures['theta_o']
        tsd['Qcs_sen'][t] = phi_c_act
        tsd['Qcs_sen_sys'][t] = phi_c_act
        tsd['Qcs_lat_sys'][t] = 0
        tsd['ma_sup_cs'][t] = 0
        tsd['m_ve_recirculation'][t] = 0

        # STEP 5 - latent and sensible heat demand of AC systems
        # ******
        if control_heating_cooling_systems.cooling_system_is_ac(bpr):

            tsd['system_status'][t] = 'AC cooling'

            air_con_model_loads_flows_temperatures = airconditioning_model.calc_hvac_cooling(tsd, t)

            # update temperatures for over cooling case
            if air_con_model_loads_flows_temperatures['q_cs_sen_hvac'] < phi_c_act:

                phi_c_act_over_cooling = air_con_model_loads_flows_temperatures['q_cs_sen_hvac']
                rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_cooling(phi_c_act_over_cooling, bpr, tsd,
                                                                                        t)
                # update temperatures
                tsd['T_int'][t] = rc_model_temperatures['T_int']
                tsd['theta_m'][t] = rc_model_temperatures['theta_m']
                tsd['theta_c'][t] = rc_model_temperatures['theta_c']
                tsd['theta_o'][t] = rc_model_temperatures['theta_o']
                tsd['system_status'][t] = 'AC over cooling'

            # update AC energy demand

            tsd['Qcs_sen_sys'][t] = air_con_model_loads_flows_temperatures['q_cs_sen_hvac']
            tsd['Qcs_lat_sys'][t] = air_con_model_loads_flows_temperatures['q_cs_lat_hvac']
            tsd['ma_sup_cs'][t] = air_con_model_loads_flows_temperatures['ma_sup_cs']
            tsd['Ta_sup_cs'][t] = air_con_model_loads_flows_temperatures['ta_sup_cs']
            tsd['Ta_re_cs'][t] = air_con_model_loads_flows_temperatures['ta_re_cs']
            tsd['m_ve_recirculation'][t] = air_con_model_loads_flows_temperatures['m_ve_hvac_recirculation']
            tsd['q_cs_lat_peop'][t] = air_con_model_loads_flows_temperatures['q_cs_lat_peop']

        # STEP 6 - emission system losses
        # ******
        q_em_ls_cooling = space_emission_systems.calc_q_em_ls_cooling(bpr, tsd, t)

        # set temperatures to tsd for cooling
        tsd['T_int'][t] = rc_model_temperatures['T_int']
        tsd['theta_m'][t] = rc_model_temperatures['theta_m']
        tsd['theta_c'][t] = rc_model_temperatures['theta_c']
        tsd['theta_o'][t] = rc_model_temperatures['theta_o']
        tsd['Qcs'][t] = 0
        tsd['Qcs_em_ls'][t] = q_em_ls_cooling
        tsd['Qcsf'][t] = 0
        tsd['Qcsf_lat'][t] = 0
        update_tsd_no_heating(tsd, t)

    detailed_thermal_balance_to_tsd(tsd, bpr, t, rc_model_temperatures, gv)

    return


def calc_heating_cooling_loads(bpr, tsd, t):

    # first check for season
    if control_heating_cooling_systems.is_heating_season(bpr=bpr, t=t) and not control_heating_cooling_systems.is_cooling_season(bpr=bpr, t=t):

        # HEATING

        # check system

        if not control_heating_cooling_systems.has_heating_system(bpr):

            # no system = no loads
            calc_rc_no_loads(bpr, tsd, t)

        elif control_heating_cooling_systems.has_radiator_heating_system(bpr):

            # radiator or floor heating
            calc_heat_loads_radiator(bpr, t, tsd)

            # update tsd
            update_tsd_no_cooling(tsd, t)

        # elif has_local_ac_heating_system:

            # calc rc model sensible demand
        #    qh_sen_rc_demand = calc_rc_heating_demand(bpr=bpr, tsd=tsd, t=t)

            # demand is load

            # no action on humidity
        #    tsd['g_hu_ld'][t] = 0  # no humidification or dehumidification
        #    tsd['g_dhu_ld'][t] = 0
        #    latent_loads.calc_moisture_content_in_zone_local(bpr, tsd, t)

            # emission losses
        #    q_em_ls_heating = space_emission_systems.calc_q_em_ls_heating(bpr, tsd, t)

        elif control_heating_cooling_systems.has_central_ac_heating_system(bpr):

            calc_heat_loads_central_ac(bpr, t, tsd)

            # update tsd
            update_tsd_no_cooling(tsd, t)

        else:
            # message and no heating system
            calc_rc_no_loads(bpr, tsd, t)

    elif control_heating_cooling_systems.is_cooling_season(bpr=bpr, t=t) and not control_heating_cooling_systems.is_heating_season(bpr=bpr, t=t):

        # COOLING

        # check system

        if not control_heating_cooling_systems.has_cooling_system(bpr):

            # no system = no loads
            calc_rc_no_loads(bpr, tsd, t)

        elif control_heating_cooling_systems.has_local_ac_cooling_system(bpr):

            calc_cool_loads_mini_split_ac(bpr, t, tsd)

            # update tsd
            update_tsd_no_heating(tsd, t)


        elif control_heating_cooling_systems.has_central_ac_cooling_system(bpr):

            calc_cool_loads_central_ac(bpr, t, tsd)

            # update tsd
            update_tsd_no_heating(tsd, t)


        elif control_heating_cooling_systems.has_3for2_cooling_system(bpr):

            calc_cool_loads_3for2(bpr, t, tsd)

            # update tsd
            update_tsd_no_heating(tsd, t)

        else:
            # message and no cooling system
            calc_rc_no_loads(bpr, tsd, t)

    else:
        warnings.warn('Timestep %s not in heating season nor cooling season' % t)
        calc_rc_no_loads(bpr, tsd, t)

    return


def calc_heat_loads_radiator(bpr, t, tsd):


    # calc rc model sensible demand
    qh_sen_rc_demand, rc_model_temperatures = calc_rc_heating_demand(bpr=bpr, tsd=tsd, t=t)

    # write temperatures to rc-model
    # rc_temperatures_to_tsd(rc_model_temperatures, tsd, t)

    # no action on humidity
    tsd['g_hu_ld'][t] = 0  # no humidification or dehumidification
    tsd['g_dhu_ld'][t] = 0
    latent_loads.calc_moisture_content_in_zone_local(bpr, tsd, t)

    # write sensible loads to tsd
    tsd['Qhs_sen_rc'][t] = tsd['Qhs_sen_shu'][t] = qh_sen_rc_demand     # demand is load
    tsd['Qhs_sen_ahu'][t] = 0
    tsd['Qhs_sen_aru'][t] = 0
    tsd['Qhs_sen_sys'][t] = qh_sen_rc_demand  # sum system loads
    # write temperatures to rc-model
    rc_temperatures_to_tsd(rc_model_temperatures, tsd, t)
    tsd['Qhs_lat_sys'][t] = 0

    # mass flows to tsd
    tsd['ma_sup_hs_ahu'][t] = 0
    tsd['ta_sup_hs_ahu'][t] = np.nan
    tsd['ta_re_hs_ahu'][t] = np.nan
    tsd['ma_sup_hs_aru'][t] = 0
    tsd['ta_sup_hs_aru'][t] = np.nan
    tsd['ta_re_hs_aru'][t] = np.nan

    # emission losses
    q_em_ls_heating = space_emission_systems.calc_q_em_ls_heating(bpr, tsd, t)
    tsd['Qhs_em_ls'][t] = q_em_ls_heating


def rc_temperatures_to_tsd(rc_model_temperatures, tsd, t):
    tsd['T_int'][t] = rc_model_temperatures['T_int']
    tsd['theta_m'][t] = rc_model_temperatures['theta_m']
    tsd['theta_c'][t] = rc_model_temperatures['theta_c']
    tsd['theta_o'][t] = rc_model_temperatures['theta_o']


def calc_heat_loads_central_ac(bpr, t, tsd):


    # get values from tsd
    m_ve_mech = tsd['m_ve_mech'][t]
    t_ve_mech_after_hex = tsd['theta_ve_mech'][t]
    x_ve_mech = tsd['x_ve_mech'][t]

    # calc rc model sensible demand
    qh_sen_rc_demand, rc_model_temperatures = calc_rc_heating_demand(bpr=bpr, tsd=tsd, t=t)
    # calc central ac unit load
    loads_ahu = airconditioning_model.central_air_handling_unit_heating(m_ve_mech, t_ve_mech_after_hex,
                                                                             x_ve_mech, bpr)
    qh_sen_central_ac_load = loads_ahu['qh_sen_ahu']

    # check for over heating
    if qh_sen_central_ac_load > qh_sen_rc_demand:

        # case: over heating
        qh_sen_aru = 0  # no additional heating via air recirculation unit

        # update rc model temperatures
        rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_heating(qh_sen_central_ac_load, bpr, tsd, t)

    elif qh_sen_central_ac_load <= qh_sen_rc_demand:

        # case: additional heating by air recirculation unit
        qh_sen_aru = qh_sen_rc_demand - qh_sen_central_ac_load

        # update of rc model not necessary

    else:
        raise Exception("Something went wrong in the central AC heating load calculation.")



    # no action on humidity
    tsd['g_hu_ld'][t] = 0  # no humidification or dehumidification
    tsd['g_dhu_ld'][t] = 0
    latent_loads.calc_moisture_content_in_zone_local(bpr, tsd, t)

    # write sensible loads to tsd
    tsd['Qhs_sen_rc'][t] = qh_sen_rc_demand
    tsd['Qhs_sen_shu'][t] = 0
    tsd['Qhs_sen_ahu'][t] = qh_sen_central_ac_load
    tsd['Qhs_sen_aru'][t] = qh_sen_aru
    rc_temperatures_to_tsd(rc_model_temperatures, tsd, t)
    tsd['Qhs_sen_sys'][t] = qh_sen_central_ac_load + qh_sen_aru  # sum system loads
    tsd['Qhs_lat_sys'][t] = 0

    # mass flows to tsd
    tsd['ma_sup_hs_ahu'][t] = loads_ahu['ma_sup_hs_ahu']
    tsd['ta_sup_hs_ahu'][t] = loads_ahu['ta_sup_hs_ahu']
    tsd['ta_re_hs_ahu'][t] = loads_ahu['ta_re_hs_ahu']

    # emission losses
    q_em_ls_heating = space_emission_systems.calc_q_em_ls_heating(bpr, tsd, t)
    tsd['Qhs_em_ls'][t] = q_em_ls_heating

def calc_cool_loads_mini_split_ac(bpr, t, tsd):

    # get values from tsd
    t_int_prev = tsd['T_int'][t-1]
    x_int_prev = tsd['x_int'][t-1]

    # calculate rc model demand
    qc_sen_rc_demand = calc_rc_cooling_demand(bpr=bpr, tsd=tsd, t=t)
    # demand is system load of air recirculation unit (ARU)
    qc_sen_aru = qc_sen_rc_demand
    # "uncontrolled" dehumidification by air recirculation unit
    g_dhu_demand_aru = 0  # no demand that controls the unit
    aru_system_loads = airconditioning_model.local_air_recirculation_unit_cooling(qc_sen_aru, g_dhu_demand_aru, t_int_prev,
                                                                          x_int_prev, t_control=True, x_control=False)
    g_dhu_aru = aru_system_loads['g_dhu_aru']
    qc_lat_aru = aru_system_loads['qc_lat_aru']
    # action on moisture
    tsd['g_hu_ld'][t] = 0  # no humidification
    tsd['g_dhu_ld'][t] = g_dhu_aru
    latent_loads.calc_moisture_content_in_zone_local(bpr, tsd, t)
    # emission losses
    q_em_ls_cooling = space_emission_systems.calc_q_em_ls_cooling(bpr, tsd, t)


def calc_cool_loads_central_ac(bpr, t, tsd):



    # get values from tsd
    m_ve_mech = tsd['m_ve_mech'][t]
    t_ve_mech_after_hex = tsd['theta_ve_mech'][t]
    x_ve_mech = tsd['x_ve_mech'][t]
    t_int_prev = tsd['T_int'][t-1]
    x_int_prev = tsd['x_int'][t-1]


    # ***
    # RC MODEL
    # ***
    # calculate rc model demand
    qc_sen_rc_demand, rc_model_temperatures = calc_rc_cooling_demand(bpr=bpr, tsd=tsd, t=t)
    # ***
    # AHU
    # ***
    # calculate ahu loads
    loads_ahu = airconditioning_model.central_air_handling_unit_cooling(m_ve_mech, t_ve_mech_after_hex, x_ve_mech, bpr)
    qc_sen_ahu = loads_ahu['qc_sen_ahu']
    qc_lat_ahu = loads_ahu['qc_lat_ahu']
    x_sup_c_ahu = tsd['x_ve_mech'][t] = loads_ahu['x_sup_c_ahu']  # update tsd['x_ve_mech'] is needed for dehumidification load calculation
    # ***
    # ARU
    # ***
    # calculate recirculation unit dehumidification demand
    # NOTE: here we might make some error, as we calculate the moisture set point for the uncorrected zone air temperature (i.e. no over cooling)
    tsd['T_int'][t] = rc_model_temperatures['T_int'] # dehumidification load needs zone temperature
    g_dhu_demand_aru = latent_loads.calc_dehumidification_moisture_load(tsd, bpr, t)
    # calculate remaining sensible demand to be attained by aru
    qc_sen_demand_aru = np.max([0, qc_sen_rc_demand - qc_sen_ahu])
    # calculate ARU system loads with T and x control activated
    aru_system_loads = airconditioning_model.local_air_recirculation_unit_cooling(qc_sen_demand_aru, g_dhu_demand_aru,
                                                                          t_int_prev, x_int_prev, bpr,
                                                                          t_control=True, x_control=True)
    g_dhu_aru = aru_system_loads['g_dhu_aru']
    qc_lat_aru = aru_system_loads['qc_lat_aru']
    qc_sen_aru = aru_system_loads['qc_sen_aru']
    # ***
    # ADJUST RC MODEL TEMPERATURE
    # ***
    # TODO: check if it is smaller, something went wrong in the calculation
    qc_sen_total = qc_sen_ahu + qc_sen_aru
    # update rc model temperatures
    rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_cooling(qc_sen_total, bpr, tsd, t)
    # ***
    # ZONE MOISTURE
    # ***
    # action on moisture
    tsd['g_hu_ld'][t] = 0  # no humidification
    tsd['g_dhu_ld'][t] = g_dhu_aru
    latent_loads.calc_moisture_content_in_zone_local(bpr, tsd, t)


    # write to tsd
    tsd['Qcs_sen_rc'][t] = qc_sen_rc_demand
    tsd['Qcs_sen_ahu'][t] = qc_sen_ahu
    tsd['Qcs_sen_aru'][t] = qc_sen_aru
    tsd['Qcs_sen_scu'][t] = 0  # not present in this system
    tsd['Qcs_lat_ahu'][t] = qc_lat_ahu
    tsd['Qcs_lat_aru'][t] = qc_lat_aru
    tsd['Qcs_sen_sys'][t] = qc_sen_ahu + qc_sen_aru  # sum system loads
    tsd['Qcs_lat_sys'][t] = qc_lat_ahu + qc_sen_aru
    rc_temperatures_to_tsd(rc_model_temperatures, tsd, t)

    # mass flows to tsd
    tsd['ma_sup_cs_ahu'][t] = loads_ahu['ma_sup_cs_ahu']
    tsd['ta_sup_cs_ahu'][t] = loads_ahu['ta_sup_cs_ahu']
    tsd['ta_re_cs_ahu'][t] = loads_ahu['ta_re_cs_ahu']
    tsd['ma_sup_cs_aru'][t] = aru_system_loads['ma_sup_cs_aru']
    tsd['ta_sup_cs_aru'][t] = aru_system_loads['ta_sup_cs_aru']
    tsd['ta_re_cs_aru'][t] = aru_system_loads['ta_re_cs_aru']

    # ***
    # emission losses
    # ***
    # emission losses on total sensible load
    # TODO: check
    q_em_ls_cooling = space_emission_systems.calc_q_em_ls_cooling(bpr, tsd, t)
    tsd['Qcs_em_ls'][t] = q_em_ls_cooling


def calc_cool_loads_3for2(bpr, t, tsd):

    # get values from tsd
    m_ve_mech = tsd['m_ve_mech'][t]
    t_ve_mech_after_hex = tsd['theta_ve_mech'][t]
    x_ve_mech = tsd['x_ve_mech'][t]
    t_int_prev = tsd['T_int'][t-1]
    x_int_prev = tsd['x_int'][t-1]



    # ***
    # RC MODEL
    # ***
    # calculate rc model demand
    qc_sen_rc_demand, rc_model_temperatures = calc_rc_cooling_demand(bpr=bpr, tsd=tsd, t=t)
    # ***
    # AHU
    # ***
    # calculate ahu loads
    ahu_loads = airconditioning_model.central_air_handling_unit_cooling(m_ve_mech, t_ve_mech_after_hex, x_ve_mech, bpr)
    qc_sen_ahu = ahu_loads['qc_sen_ahu']
    qc_lat_ahu = ahu_loads['qc_lat_ahu']
    x_sup_c_ahu = tsd['x_ve_mech'][t] = ahu_loads['x_sup_c_ahu']
    # ***
    # ARU
    # ***
    # calculate recirculation unit dehumidification demand
    tsd['T_int'][t] = rc_model_temperatures['T_int'] # dehumidification load needs zone temperature
    # NOTE: here we might make some error, as we calculate the moisture set point for the uncorrected zone air temperature (i.e. no over cooling)
    g_dhu_demand_aru = latent_loads.calc_dehumidification_moisture_load(tsd, bpr, t)
    # no sensible demand that controls the ARU
    qc_sen_demand_aru = 0
    # calculate ARU system loads with T and x control activated
    aru_system_loads = airconditioning_model.local_air_recirculation_unit_cooling(qc_sen_demand_aru, g_dhu_demand_aru,
                                                                          t_int_prev, x_int_prev, bpr,
                                                                          t_control=False, x_control=True)
    g_dhu_aru = aru_system_loads['g_dhu_aru']
    qc_lat_aru = aru_system_loads['qc_lat_aru']
    qc_sen_aru = aru_system_loads['qc_sen_aru']
    # ***
    # SCU
    # ***
    # calculate remaining sensible cooling demand to be met by radiative cooling
    qc_sen_demand_scu = np.min([0, qc_sen_rc_demand - qc_sen_ahu - qc_sen_aru])
    # demand is load
    qc_sen_scu = qc_sen_demand_scu
    # ***
    # ADJUST RC MODEL TEMPERATURE
    # ***
    # TODO: check, if it is smaller something went wrong in the calculation
    qc_sen_total = qc_sen_ahu + qc_sen_aru + qc_sen_scu
    # update rc model temperatures
    rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_cooling(qc_sen_total, bpr, tsd, t)
    # ***
    # ZONE MOISTURE
    # ***
    # action on moisture
    tsd['g_hu_ld'][t] = 0  # no humidification
    tsd['g_dhu_ld'][t] = g_dhu_aru
    latent_loads.calc_moisture_content_in_zone_local(bpr, tsd, t)
    # ***
    # emission losses
    # ***
    # emission losses on total sensible load
    # TODO: check

    # write to tsd
    tsd['Qcs_sen_rc'][t] = qc_sen_rc_demand
    tsd['Qcs_sen_ahu'][t] = qc_sen_ahu
    tsd['Qcs_sen_aru'][t] = qc_sen_aru
    tsd['Qcs_sen_scu'][t] = qc_sen_scu
    tsd['Qcs_lat_ahu'][t] = qc_lat_ahu
    tsd['Qcs_lat_aru'][t] = qc_lat_aru
    rc_temperatures_to_tsd(rc_model_temperatures, tsd, t)
    tsd['Qcs_sen_sys'][t] = qc_sen_ahu + qc_sen_aru + qc_sen_scu # sum system loads
    tsd['Qcs_lat_sys'][t] = qc_lat_ahu + qc_sen_aru

    # mass flows to tsd
    tsd['ma_sup_cs_ahu'][t] = ahu_loads['ma_sup_cs_ahu']
    tsd['ta_sup_cs_ahu'][t] = ahu_loads['ta_sup_cs_ahu']
    tsd['ta_re_cs_ahu'][t] = ahu_loads['ta_re_cs_ahu']
    tsd['ma_sup_cs_aru'][t] = aru_system_loads['ma_sup_cs_aru']
    tsd['ta_sup_cs_aru'][t] = aru_system_loads['ta_sup_cs_aru']
    tsd['ta_re_cs_aru'][t] = aru_system_loads['ta_re_cs_aru']


    q_em_ls_cooling = space_emission_systems.calc_q_em_ls_cooling(bpr, tsd, t)
    tsd['Qcs_em_ls'][t] = q_em_ls_cooling


def update_tsd_no_heating(tsd, t):
    """
    updates NaN values in tsd for case of no heating demand

    Author: Gabriel Happle
    Date: 01/2017

    :param tsd: time series data dict
    :param t: time step / hour of year [0..8760]
    :return: updates tsd values
    """

    # no sensible loads
    tsd['Qhs_sen_rc'][t] = 0
    tsd['Qhs_sen_shu'][t] = 0
    tsd['Qhs_sen_aru'][t] = 0
    tsd['Qhs_sen_ahu'][t] = 0

    # no latent loads
    tsd['Qhs_lat_aru'][t] = 0
    tsd['Qhs_lat_ahu'][t] = 0


    #tsd['Qhs_sen'][t] = 0
    tsd['Qhs_sen_sys'][t] = 0
    tsd['Qhs_lat_sys'][t] = 0
    tsd['Qhs_em_ls'][t] = 0
    #tsd['ma_sup_hs'][t] = 0
    #tsd['Ta_sup_hs'][t] = 0  # TODO: this is dangerous as there is no temperature needed, 0 is necessary for 'calc_temperatures_emission_systems' to work
    #tsd['Ta_re_hs'][t] = 0  # TODO: this is dangerous as there is no temperature needed, 0 is necessary for 'calc_temperatures_emission_systems' to work
    #tsd['Ehs_lat_aux'][t] = 0
    #tsd['m_ve_recirculation'][t] = 0

    # mass flows to tsd
    tsd['ma_sup_hs_ahu'][t] = 0
    tsd['ta_sup_hs_ahu'][t] = np.nan
    tsd['ta_re_hs_ahu'][t] = np.nan
    tsd['ma_sup_hs_aru'][t] = 0
    tsd['ta_sup_hs_aru'][t] = np.nan
    tsd['ta_re_hs_aru'][t] = np.nan


    return


def update_tsd_no_cooling(tsd, t):
    """
    updates NaN values in tsd for case of no cooling demand

    Author: Gabriel Happle
    Date: 01/2017

    :param tsd: time series data dict
    :param t: time step / hour of year [0..8760]
    :return: updates tsd values
    """

    # no sensible loads
    tsd['Qcs_sen_rc'][t] = 0
    tsd['Qcs_sen_scu'][t] = 0
    tsd['Qcs_sen_aru'][t] = 0
    tsd['Qcs_sen_ahu'][t] = 0

    # no latent loads
    tsd['Qcs_lat_aru'][t] = 0
    tsd['Qcs_lat_ahu'][t] = 0

    # no losses


    #tsd['Qcs_sen'][t] = 0
    tsd['Qcs_sen_sys'][t] = 0
    tsd['Qcs_lat_sys'][t] = 0
    tsd['Qcs_em_ls'][t] = 0
    #tsd['ma_sup_cs'][t] = 0
    #tsd['Ta_sup_cs'][t] = 0  # TODO: this is dangerous as there is no temperature needed, 0 is necessary for 'calc_temperatures_emission_systems' to work
    #tsd['Ta_re_cs'][t] = 0  # TODO: this is dangerous as there is no temperature needed, 0 is necessary for 'calc_temperatures_emission_systems' to work
    #tsd['m_ve_recirculation'][t] = 0

    # mass flows to tsd
    tsd['ma_sup_cs_ahu'][t] = 0
    tsd['ta_sup_cs_ahu'][t] = np.nan
    tsd['ta_re_cs_ahu'][t] = np.nan
    tsd['ma_sup_cs_aru'][t] = 0
    tsd['ta_sup_cs_aru'][t] = np.nan
    tsd['ta_re_cs_aru'][t] = np.nan


    return


def detailed_thermal_balance_to_tsd(tsd, bpr, t, rc_model_temperatures, gv):

    # internal gains from lights
    tsd['Qgain_light'][t] = rc_model_SIA.calc_phi_i_l(tsd['Elf'][t])
    # internal gains from appliances, data centres and losses from refrigeration
    tsd['Qgain_app'][t] = rc_model_SIA.calc_phi_i_a(tsd['Eaf'][t], 0, 0)
    tsd['Qgain_data'][t] = tsd['Qcdataf'][t]
    tsd['Q_cool_ref'] = -tsd['Qcref'][t]
    # internal gains from people
    tsd['Qgain_pers'][t] = rc_model_SIA.calc_phi_i_p(tsd['Qs'][t])

    # losses / gains from ventilation
    #tsd['']

    # extract detailed rc model intermediate results
    h_em = rc_model_temperatures['h_em']
    h_op_m = rc_model_temperatures['h_op_m']
    theta_m = rc_model_temperatures['theta_m']
    theta_em = rc_model_temperatures['theta_em']
    h_ec = rc_model_temperatures['h_ec']
    theta_c = rc_model_temperatures['theta_c']
    theta_ec = rc_model_temperatures['theta_ec']
    h_ea = rc_model_temperatures['h_ea']
    T_int = rc_model_temperatures['T_int']
    theta_ea = rc_model_temperatures['theta_ea']

    # backwards calculate individual heat transfer coefficient
    h_wall_em = h_em * bpr.rc_model['Aop_sup'] * bpr.rc_model['U_wall'] / h_op_m
    h_base_em = h_em * bpr.rc_model['Aop_bel'] * gv.Bf * bpr.rc_model['U_base'] / h_op_m
    h_roof_em = h_em * bpr.rc_model['Aroof'] * bpr.rc_model['U_roof'] / h_op_m

    # calculate heat fluxes between mass and outside through opaque elements
    tsd['Qgain_wall'][t] = h_wall_em * (theta_em - theta_m)
    tsd['Qgain_base'][t] = h_base_em * (theta_em - theta_m)
    tsd['Qgain_roof'][t] = h_roof_em * (theta_em - theta_m)

    # calculate heat fluxes between central and outside through windows
    tsd['Qgain_wind'][t] = h_ec * (theta_ec - theta_c)

    # calculate heat between outside and inside air through ventilation
    tsd['Qgain_vent'][t] = h_ea * (theta_ea - T_int)

    return


def calc_rc_no_loads(bpr, tsd, t):

    # STEP 1
    # ******
    # calculate temperatures
    rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_no_heating_cooling(bpr, tsd, t)

    # calculate humidity
    tsd['g_hu_ld'][t] = 0  # no humidification or dehumidification
    tsd['g_dhu_ld'][t] = 0
    latent_loads.calc_moisture_content_in_zone_local(bpr, tsd, t)

    # write to tsd
    tsd['T_int'][t] = rc_model_temperatures['T_int']
    tsd['theta_m'][t] = rc_model_temperatures['theta_m']
    tsd['theta_c'][t] = rc_model_temperatures['theta_c']
    tsd['theta_o'][t] = rc_model_temperatures['theta_o']
    update_tsd_no_cooling(tsd, t)
    update_tsd_no_heating(tsd, t)
    tsd['system_status'][t] = 'systems off'


def calc_rc_heating_demand(bpr, tsd, t):

    # STEP 1
    # ******
    # calculate temperatures with 0 heating power
    rc_model_temperatures_0 = rc_model_SIA.calc_rc_model_temperatures_no_heating_cooling(bpr, tsd, t)

    T_int_0 = rc_model_temperatures_0['T_int']


    # CHECK FOR DEMAND
    if not rc_model_SIA.has_sensible_heating_demand(T_int_0, tsd, t):

        # return zero demand
        rc_model_temperatures = rc_model_temperatures_0
        phi_h_act = 0

    elif rc_model_SIA.has_sensible_heating_demand(T_int_0, tsd, t):
        # continue

        # STEP 2
        # ******
        # calculate temperatures with 10 W/m2 heating power
        phi_hc_10 = 10 * bpr.rc_model['Af']
        rc_model_temperatures_10 = rc_model_SIA.calc_rc_model_temperatures_heating(phi_hc_10, bpr, tsd, t)

        T_int_10 = rc_model_temperatures_10['T_int']

        T_int_set = tsd['ta_hs_set'][t]

        # interpolate heating power
        # (64) in SIA 2044 / Korrigenda C1 zum Merkblatt SIA 2044:2011 / Korrigenda C2 zum Mekblatt SIA 2044:2011
        phi_hc_ul = phi_hc_10*(T_int_set - T_int_0) / (T_int_10 - T_int_0)

        # STEP 3
        # ******
        # check if available power is sufficient
        phi_h_max = bpr.hvac['Qhsmax_Wm2'] * bpr.rc_model['Af']

        if 0 < phi_hc_ul <= phi_h_max:
            # case heating with phi_hc_ul
            # calculate temperatures with this power
            phi_h_act = phi_hc_ul

        elif 0 < phi_hc_ul > phi_h_max:
            # case heating with max power available
            # calculate temperatures with this power
            phi_h_act = phi_h_max
        else:
            raise Exception("something went wrong")

        # STEP 4
        # ******
        rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_heating(phi_h_act, bpr, tsd, t)

    else:
        raise

    # write necessary parameters for AC calculation to tsd
    #tsd['T_int'][t] = rc_model_temperatures['T_int']
    #tsd['theta_m'][t] = rc_model_temperatures['theta_m']
    #tsd['theta_c'][t] = rc_model_temperatures['theta_c']
    #tsd['theta_o'][t] = rc_model_temperatures['theta_o']
    #tsd['Qhs_sen'][t] = phi_h_act
    #tsd['Qhs_sen_sys'][t] = phi_h_act
    #tsd['Qhs_lat_sys'][t] = 0
    #tsd['Ehs_lat_aux'][t] = 0
    #tsd['ma_sup_hs'][t] = 0
    #tsd['Ta_sup_hs'][t] = 0
    #tsd['Ta_re_hs'][t] = 0
    #tsd['m_ve_recirculation'][t] = 0

    return phi_h_act, rc_model_temperatures


def calc_rc_cooling_demand(bpr, tsd, t):

    # ++++++++++++++++
    # CASE 2 - COOLING
    # ++++++++++++++++
    # case for cooling
    #tsd['system_status'][t] = 'Radiative cooling'

    # STEP 1
    # ******
    # calculate temperatures with 0 heating power
    rc_model_temperatures_0 = rc_model_SIA.calc_rc_model_temperatures_no_heating_cooling(bpr, tsd, t)

    T_int_0 = rc_model_temperatures_0['T_int']

    # CHECK FOR DEMAND
    if not rc_model_SIA.has_sensible_cooling_demand(T_int_0, tsd, t):

        # return zero demand
        rc_model_temperatures = rc_model_temperatures_0
        phi_c_act = 0

    elif rc_model_SIA.has_sensible_cooling_demand(T_int_0, tsd, t):
        # continue

        # STEP 2
        # ******
        # calculate temperatures with 10 W/m2 cooling power
        phi_hc_10 = 10 * bpr.rc_model['Af']
        rc_model_temperatures_10 = rc_model_SIA.calc_rc_model_temperatures_cooling(phi_hc_10, bpr, tsd, t)

        T_int_10 = rc_model_temperatures_10['T_int']

        T_int_set = tsd['ta_cs_set'][t]

        # interpolate heating power
        # (64) in SIA 2044 / Korrigenda C1 zum Merkblatt SIA 2044:2011 / Korrigenda C2 zum Mekblatt SIA 2044:2011
        phi_hc_ul = phi_hc_10 * (T_int_set - T_int_0) / (T_int_10 - T_int_0)

        # STEP 3
        # ******
        # check if available power is sufficient
        phi_c_max = -bpr.hvac['Qcsmax_Wm2'] * bpr.rc_model['Af']

        if 0 > phi_hc_ul >= phi_c_max:
            # case heating with phi_hc_ul
            # calculate temperatures with this power
            phi_c_act = phi_hc_ul

        elif 0 > phi_hc_ul < phi_c_max:
            # case heating with max power available
            # calculate temperatures with this power
            phi_c_act = phi_c_max

        else:
            raise Exception("ups something went wrong")

        # STEP 4
        # ******
        rc_model_temperatures = rc_model_SIA.calc_rc_model_temperatures_cooling(phi_c_act, bpr, tsd, t)

    else:
        raise

    # write necessary parameters for AC calculation to tsd
    #tsd['T_int'][t] = rc_model_temperatures['T_int']
    #tsd['theta_m'][t] = rc_model_temperatures['theta_m']
    #tsd['theta_c'][t] = rc_model_temperatures['theta_c']
    #tsd['theta_o'][t] = rc_model_temperatures['theta_o']
    #tsd['Qcs_sen'][t] = phi_c_act
    #tsd['Qcs_sen_sys'][t] = phi_c_act
    #tsd['Qcs_lat_sys'][t] = 0
    #tsd['ma_sup_cs'][t] = 0
    #tsd['m_ve_recirculation'][t] = 0

    return phi_c_act, rc_model_temperatures