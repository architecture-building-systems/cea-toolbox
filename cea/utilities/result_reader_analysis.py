"""
Read CEA results over all scenarios in a project and produce commonly used UBEM metrics.
The list of UBEM metrics include:

- EUI - Grid Electricity [kWh/m²/yr]
  - Annual
- EUI - Enduse Electricity [kWh/m²/yr]
  - Annual
- EUI - Cooling Demand [kWh/m²/yr]
  - Annual
- EUI - Space Cooling Demand [kWh/m²/yr]
  - Annual
- EUI - Heating Demand [kWh/m²/yr]
  - Annual
- EUI - Space Heating Demand [kWh/m²/yr]
  - Annual
- EUI - Domestic Hot Water Demand [kWh/m²/yr]
  - Annual
- PV Energy Penetration [-]
  - Annual
- PV Self-Consumption [-]
  - Annual
- PV Energy Sufficiency [-]
  - Annual
- PV Self-Sufficiency [-]
  - Annual
- PV Capacity Factor [-]
  - Annual
- PV Specific Yield [-]
  - Annual
  - Winter, Spring, Summer, Autumn
  - Winter+Hourly, Spring+Hourly, Summer+Hourly, Autumn+Hourly
  - Daily
  - Weekly
  - Monthly
- PV System Emissions [kgCO₂]
  - Annual
- PV Generation Intensity [kgCO₂/kWh]
  - Annual
  - Winter, Spring, Summer, Autumn
  - Winter+Hourly, Spring+Hourly, Summer+Hourly, Autumn+Hourly
  - Daily
  - Weekly
  - Monthly
- DH Plant Capacity Factor [-]
  - Annual
- DH Pump Capacity Factor [-]
  - Annual
- DC Plant Capacity Factor [-]
  - Annual
- DC Pump Capacity Factor [-]
  - Annual

"""

import os
# import warnings
import numpy as np
import pandas as pd
import cea.config
import time
from cea.utilities.date import get_date_range_hours_from_year
from cea.utilities.date import generate_season_masks
from cea.technologies.solar.photovoltaic import projected_lifetime_output

# warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)


__author__ = "Zhongming Shi, Reynold Mok, Justin McCarty"
__copyright__ = "Copyright 2024, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Zhongming Shi, Reynold Mok, Justin McCarty"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"


def calc_capacity_factor(gen_kwh, max_kw):
    """
    caculate the capacity factor of a device

    :param gen_kwh: energy output over a time period
    :type gen_kwh: float or series
    :param max_kw: peak capacity of the system
    :type max_kw: float
    Returns:
    -------
    capacity_factor: float
        the unitless ratio of actual energy output over a year to the theoretical maximum energy output over that period.

    """
    if type(gen_kwh) == float:
        len_time_period = 8760
    else:
        len_time_period = len(gen_kwh)
    sum_kWh = gen_kwh.sum()
    capacity_factor = sum_kWh / (max_kw * len_time_period)

    return capacity_factor


def calc_specific_yield(gen_kwh, max_kw, time_period="annual"):
    """
    Calculate the specific yield of the system
    Authors:
    - Justin McCarty

    Parameters:
    ----------
    gen_kwh : pd.Series
        The hourly annual energy generation [kWh] with a DatetimeIndex.
    max_kw: float
        The peak capacity of the system [kWp]
    time_period : str
        The time period over which to calculate self-consumption.
        Options:
            - "annual"
            - "winter", "spring", "summer", "autumn"
            - "1", "2, "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"
    Returns:
    -------
    float
        The calculated specific yield.

    Raises:
    ------
    TypeError:
        - If the input data is not a pandas.Series.
    ValueError:
        - If the `time_period` is invalid.
    """

    # Validate inputs
    if not isinstance(gen_kwh, pd.Series):
        raise TypeError("Both gen_kwh must be Pandas Series.")

    datetime_idx = get_date_range_hours_from_year(2025)

    # Combine the two Series into a DataFrame
    df = pd.DataFrame({"gen_kwh": gen_kwh.values},
                      index=datetime_idx)

    # Calculate self_consumption based on the time_period
    if time_period == "annual":
        annual_gen = df['gen_kwh'].sum()
        specific_yield = annual_gen / max_kw

    elif time_period in ["winter", "spring", "summer", "autumn"]:
        season_mask_dict = generate_season_masks(df)
        if time_period not in season_mask_dict:
            raise ValueError(f"Invalid season specified: {time_period}")

        season_mask = season_mask_dict[time_period]
        season_gen = df.loc[season_mask, 'gen_kwh'].sum()
        specific_yield = season_gen / max_kw

    elif time_period in [str(m) for m in range(1, 13)]:
        month_gen = df.resample("M").sum().iloc[int(time_period)-1]
        specific_yield = month_gen / max_kw

    else:
        print(f"In calc_specific_yield, the argument 'time_period' was not specified correctly ({time_period}). Using 'annual' by default.")
        annual_gen = df['gen_kwh'].sum()
        specific_yield = annual_gen / max_kw

    return specific_yield


def calc_self_consumption(gen_kwh, demand_kWh, time_period='annual'):
    """
    Calculates self-consumption based on the specified time period.
    Authors:
    - Zhongming Shi
    - Justin McCarty

    Parameters:
    ----------
    gen_kwh : pd.Series
        The hourly annual energy generation [kWh] with a DatetimeIndex.
    demand_kWh : pd.Series
        The hourly annual energy load [kWh] with a DatetimeIndex.
    time_period : str
        The time period over which to calculate self-consumption.
        Options:
            - "annual"
            - "seasonal"
            - "winter", "spring", "summer", "autumn"
            - "winter+hourly", "spring+hourly", "summer+hourly", "autumn+hourly"
            - "daily", "weekly", "monthly"
            - "hourly"

    Returns:
    -------
    float
        The calculated self-consumption ratio.

    Raises:
    ------
    TypeError:
        - If the input data is not a pandas.Series.
    ValueError:
        - If the `time_period` is invalid.
    ZeroDivisionError:
        - If the total generated kWh for a period is zero.
    """

    # Validate inputs
    if not isinstance(gen_kwh, pd.Series) or not isinstance(demand_kWh, pd.Series):
        raise TypeError("Both gen_kwh_df and demand_kWh_df must be Pandas Series.")

    datetime_idx = get_date_range_hours_from_year(2025)

    # Combine the two Series into a DataFrame
    df = pd.DataFrame({"gen_kwh": gen_kwh.values, "demand_kWh": demand_kWh.values},
                      index=datetime_idx)

    # Calculate self_consumption based on the time_period
    if time_period == "annual":
        df_resample = df.resample("A").sum()  # "" stands for year-end frequency
        use = df_resample.min(axis=1)
        total_gen = df['gen_kwh'].sum()
        if total_gen == 0:
            raise ZeroDivisionError("Total generated kWh is zero, cannot divide by zero.")
        self_consumption = use.sum() / total_gen

    elif time_period == "seasonal":
        season_mask_dict = generate_season_masks(df)
        season_results = []
        for season, mask in season_mask_dict.items():
            season_sum = df[mask].sum().rename(season)
            season_results.append(season_sum)
        season_data = pd.concat(season_results, axis=1)
        min_per_season = season_data.min(axis=0)
        total_gen = df['gen_kwh'].sum()
        if total_gen == 0:
            raise ZeroDivisionError("Total generated kWh is zero, cannot divide by zero.")
        self_consumption = min_per_season.sum() / total_gen

    elif time_period in ["winter", "spring", "summer", "autumn", "winter+hourly", "spring+hourly", "summer+hourly",
                         "autumn+hourly"]:
        # Extract the base season
        base_season = time_period.split("+")[0]

        season_mask_dict = generate_season_masks(df)
        if base_season not in season_mask_dict:
            raise ValueError(f"Invalid season specified: {base_season}")
        season_mask = season_mask_dict[base_season]
        season_gen = df.loc[season_mask, 'gen_kwh'].sum()
        season_demand = df.loc[season_mask, 'demand_kWh'].sum()

        if time_period.endswith("+hourly"):
            if base_season not in season_mask_dict:
                raise ValueError(f"Invalid season specified: {base_season}")

            season_mask = season_mask_dict[base_season]
            season_data = df.loc[season_mask]
            use = season_data.min(axis=1).sum()
            total_gen = season_data['gen_kwh'].sum()
            if total_gen == 0:
                raise ZeroDivisionError("Total generated kWh for the season is zero, cannot divide by zero.")
            self_consumption = use / total_gen
        else:
            # Without '+hourly'
            if season_gen == 0:
                raise ZeroDivisionError(f"Total generated kWh for {time_period} is zero, cannot divide by zero.")
            self_consumption = min(season_gen, season_demand) / season_gen

    elif time_period in ["daily", "weekly", "monthly"]:
        freq_codes = {"daily": "D", "weekly": "W", "monthly": "M"}
        resample_code = freq_codes.get(time_period)
        if resample_code is None:
            raise ValueError(f"Invalid time_period: {time_period}. Choose from 'daily', 'weekly', or 'monthly'.")
        df_resample = df.resample(resample_code).sum()
        use = df_resample.min(axis=1)
        total_gen = df['gen_kwh'].sum()
        if total_gen == 0:
            raise ZeroDivisionError("Total generated kWh is zero, cannot divide by zero.")
        self_consumption = use.sum() / total_gen

    elif time_period == "hourly":
        use = df.min(axis=1).sum()
        total_gen = df['gen_kwh'].sum()
        if total_gen == 0:
            raise ZeroDivisionError("Total generated kWh is zero, cannot divide by zero.")
        self_consumption = use / total_gen

    else:
        print(f"In calc_self_consumption, the argument 'time_period' was not specified correctly ({time_period}). Using 'hourly' by default.")
        use = df.min(axis=1).sum()
        total_gen = df['gen_kwh'].sum()
        if total_gen == 0:
            raise ZeroDivisionError("Total generated kWh is zero, cannot divide by zero.")
        self_consumption = use / total_gen

    return self_consumption


def calc_self_sufficiency(gen_kwh, demand_kWh, time_period='annual'):
    """
    Calculates self-sufficiency based on the specified time period.
    Authors:
    - Zhongming Shi
    - Justin McCarty

    Parameters:
    ----------
    gen_kwh : pd.Series
        The hourly annual energy generation [kWh] with a DatetimeIndex.
    demand_kWh : pd.Series
        The hourly annual energy load [kWh] with a DatetimeIndex.
    time_period : str
        The time period over which to calculate self-sufficiency.
        Options:
            - "annual"
            - "seasonal"
            - "winter", "spring", "summer", "autumn"
            - "winter+hourly", "spring+hourly", "summer+hourly", "autumn+hourly"
            - "daily", "weekly", "monthly"
            - "hourly"

    Returns:
    -------
    float
        The calculated self-sufficiency ratio.

    Raises:
    ------
    TypeError:
        - If the input data is not a pandas.Series.
    ValueError:
        - If the `time_period` is invalid.
    ZeroDivisionError:
        - If the total generated kWh for a period is zero.
    """

    # Validate inputs
    if not isinstance(gen_kwh, pd.Series) or not isinstance(demand_kWh, pd.Series):
        raise TypeError("Both gen_kwh_df and demand_kWh_df must be Pandas Series.")

    datetime_idx = get_date_range_hours_from_year(2025)

    # Combine the two Series into a DataFrame
    df = pd.DataFrame({"gen_kwh": gen_kwh.values, "demand_kWh": demand_kWh.values},
                      index=datetime_idx)

    # Calculate self_consumption based on the time_period
    if time_period == "annual":
        df_resample = df.resample("A").sum()  # "A" stands for year-end frequency
        use = df_resample.min(axis=1)
        total_demand = df['demand_kWh'].sum()
        if total_demand == 0:
            raise ZeroDivisionError("Total demand kWh is zero, cannot divide by zero.")
        self_sufficiency = use.sum() / total_demand

    elif time_period == "seasonal":
        season_mask_dict = generate_season_masks(df)
        season_results = []
        for season, mask in season_mask_dict.items():
            season_sum = df[mask].sum().rename(season)
            season_results.append(season_sum)
        season_data = pd.concat(season_results, axis=1)
        min_per_season = season_data.min(axis=0)
        total_demand = df['demand_kWh'].sum()
        if total_demand == 0:
            raise ZeroDivisionError("Total demand kWh is zero, cannot divide by zero.")
        self_sufficiency = min_per_season.sum() / total_demand

    elif time_period in ["winter", "spring", "summer", "autumn", "winter+hourly", "spring+hourly", "summer+hourly",
                         "autumn+hourly"]:
        # Extract the base season
        base_season = time_period.split("+")[0]

        season_mask_dict = generate_season_masks(df)
        if base_season not in season_mask_dict:
            raise ValueError(f"Invalid season specified: {base_season}")
        season_mask = season_mask_dict[base_season]
        season_gen = df.loc[season_mask, 'gen_kwh'].sum()
        season_demand = df.loc[season_mask, 'demand_kWh'].sum()

        if time_period.endswith("+hourly"):
            if base_season not in season_mask_dict:
                raise ValueError(f"Invalid season specified: {base_season}")

            season_mask = season_mask_dict[base_season]
            season_data = df.loc[season_mask]
            use = season_data.min(axis=1).sum()
            total_demand = season_data['demand_kWh'].sum()
            if total_demand == 0:
                raise ZeroDivisionError("Total demand kWh for the season is zero, cannot divide by zero.")
            self_sufficiency = use / total_demand
        else:
            # Without '+hourly'
            if season_demand == 0:
                raise ZeroDivisionError(f"Total demand kWh for {time_period} is zero, cannot divide by zero.")
            self_sufficiency = min(season_gen, season_demand) / season_demand

    elif time_period in ["daily", "weekly", "monthly"]:
        freq_codes = {"daily": "D", "weekly": "W", "monthly": "M"}
        resample_code = freq_codes.get(time_period)
        if resample_code is None:
            raise ValueError(f"Invalid time_period: {time_period}. Choose from 'daily', 'weekly', or 'monthly'.")
        df_resample = df.resample(resample_code).sum()
        use = df_resample.min(axis=1)
        total_demand = df['demand_kWh'].sum()
        if total_demand == 0:
            raise ZeroDivisionError("Total demand kWh is zero, cannot divide by zero.")
        self_sufficiency = use.sum() / total_demand

    elif time_period == "hourly":
        use = df.min(axis=1).sum()
        total_demand = df['demand_kWh'].sum()
        if total_demand == 0:
            raise ZeroDivisionError("Total demand kWh is zero, cannot divide by zero.")
        self_sufficiency = use.sum() / total_demand

    else:
        print(f"The argument 'time_period' was not specified correctly ({time_period}). Using 'hourly' by default.")
        use = df.min(axis=1).sum()
        total_demand = df['demand_kWh'].sum()
        if total_demand == 0:
            raise ZeroDivisionError("Total demand kWh is zero, cannot divide by zero.")
        self_sufficiency = use.sum() / total_demand

    return self_sufficiency


def calc_generation_intensity(generator_embodied_emissions_kgco2, lifetime_electricity_generated_kwh,
                              time_period="annual"):
    """
    Calculates self-sufficiency based on the specified time period.
    Authors:
    - Justin McCarty

    Parameters:
    ----------
    generator_embodied_emissions_kgco2 : float
        the emboided emissions assocated to the generation device in kgCO2e
    lifetime_electricity_generated_kwh : pd.Series
        The sum of lifetime generation for each hour of the year in kWh
    time_period : str
        The time period over which to calculate self-sufficiency.
        Options:
            - "annual"
            - "winter", "spring", "summer", "autumn"
            - "1", "2, "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"

    Returns:
    -------
    float
        The calculated generation intensity of the generation device in kgCO2e/kWh.

    Raises:
    ------
    TypeError:
        - If the input data is not a pandas.Series.
    ValueError:
        - If the `time_period` is invalid.
    ZeroDivisionError:
        - If the total generated kWh for a period is zero.
    """

    # Validate inputs
    if not isinstance(lifetime_electricity_generated_kwh, np.ndarray):
        raise TypeError("Both gen_kwh must be numpy array.")

    datetime_idx = get_date_range_hours_from_year(2025)

    # Combine the two Series into a DataFrame
    df = pd.DataFrame({"gen_kwh": lifetime_electricity_generated_kwh},
                      index=datetime_idx)

    # Calculate self_consumption based on the time_period
    if time_period == "annual":
        annual_gen = df['gen_kwh'].sum()
        module_generation_intensity_kgco2kwh = generator_embodied_emissions_kgco2 / annual_gen

    elif time_period in ["winter", "spring", "summer", "autumn"]:
        season_mask_dict = generate_season_masks(df)
        if time_period not in season_mask_dict:
            raise ValueError(f"Invalid season specified: {time_period}")

        season_mask = season_mask_dict[time_period]
        season_gen = df.loc[season_mask, 'gen_kwh'].sum()
        module_generation_intensity_kgco2kwh = generator_embodied_emissions_kgco2 / season_gen

    elif time_period in [str(m) for m in range(1, 13)]:
        month_gen = df.resample("M").sum().iloc[int(time_period)-1].values[0]
        module_generation_intensity_kgco2kwh = generator_embodied_emissions_kgco2 / month_gen

    else:
        print(f"In calc_generation_intensity, the argument 'time_period' was not specified correctly ({time_period}). Using 'annual' by default.")
        annual_gen = df['gen_kwh'].sum()
        module_generation_intensity_kgco2kwh = generator_embodied_emissions_kgco2 / annual_gen

    return module_generation_intensity_kgco2kwh

def calc_simple_pv_payback(annual_generation_kwh, annual_electricity_demand_kwh, system_capital_cost, system_operating_rate, lifetime, interest_rate, electricity_purchase_cost, electricity_sell_value):


    return lifetime


def exec_read_and_analyse(cea_scenario):
    """
    read the CEA results and calculates the UBEM metrics listed at the top of this script

    :param cea_scenario: path to the CEA scenario to be assessed using CEA
    :type cea_scenario: file path
    Returns:
    -------
    analysis_df: pd.DataFrame
        A dataframe of the metrics at the top of this script.

    """

    # start by checking for demand data
    cea_result_demand_hourly_df = pd.DataFrame()
    total_demand_buildings_path = os.path.join(cea_scenario, 'outputs/data/demand/Total_demand.csv')
    try:
        cea_result_total_demand_buildings_df = pd.read_csv(total_demand_buildings_path)
    except FileNotFoundError:
        print(
            f"File {total_demand_buildings_path} not found. All building demand results currently required for analysis. Returning empty dataframe")
        cea_result_total_demand_buildings_df = pd.DataFrame
        return cea_result_total_demand_buildings_df

    demand_dir = os.path.join(cea_scenario, 'outputs/data/demand')
    demand_by_building = os.listdir(demand_dir)

    for file in demand_by_building:
        try:
            if file.endswith('.csv') and not file.startswith('Total_demand.csv'):
                demand_building_path = os.path.join(demand_dir, file)
                cea_result_demand_building_df = pd.DataFrame()
                cea_result_demand_building_df['GRID_kWh'] = pd.read_csv(demand_building_path)['GRID_kWh']
                cea_result_demand_hourly_df = pd.concat([cea_result_demand_building_df, cea_result_demand_hourly_df],
                                                        axis=1).reindex(cea_result_demand_building_df.index)
            else:
                pass
            cea_result_demand_hourly_df.loc[:, 'district_GRID_kWh'] = cea_result_demand_hourly_df.sum(axis=1)
        except FileNotFoundError:
            print(f"File {file} not found. All building demand results currently required for analysis. Returning empty dataframe")
            return cea_result_demand_hourly_df


    # create an empty DataFrame to store all the results
    analysis_results_dict = dict()
    analysis_results_dict['scenario_name'] = cea_scenario

    # intialize the time periods
    # Todo this should be a config option?
    time_period_options_autarky = [
        "annual",
        "seasonal",
        "winter",
        "spring",
        "summer",
        "autumn",
        "winter+hourly",
        "spring+hourly",
        "summer+hourly",
        "autumn+hourly",
        "daily",
        "weekly",
        "monthly",
        "hourly"
    ]

    time_period_options_yield = [
        "annual",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
        "winter",
        "spring",
        "summer",
        "autumn"
    ]

    time_period_options_generation_intensity = time_period_options_yield

    # not found message to be reflected in the analysis DataFrame
    na = float('Nan')

    # metrics: EUI or energy demand-related
    try:
        demand_buildings_path = os.path.join(cea_scenario, 'outputs/data/demand/Total_demand.csv')
        cea_result_total_demand_buildings_df = pd.read_csv(demand_buildings_path)
        analysis_results_dict['EUI - grid electricity [kWh/m2/yr]'] = cea_result_total_demand_buildings_df['GRID_MWhyr'].sum() / \
                                                            cea_result_total_demand_buildings_df['GFA_m2'].sum() * 1000
        analysis_results_dict['EUI - enduse electricity [kWh/m2/yr]'] = cea_result_total_demand_buildings_df[
                                                                  'E_sys_MWhyr'].sum().sum() / \
                                                              cea_result_total_demand_buildings_df['GFA_m2'].sum() * 1000
        analysis_results_dict['EUI - cooling demand [kWh/m2/yr]'] = cea_result_total_demand_buildings_df['QC_sys_MWhyr'].sum() / \
                                                          cea_result_total_demand_buildings_df['GFA_m2'].sum() * 1000
        analysis_results_dict['EUI - space cooling demand [kWh/m2/yr]'] = cea_result_total_demand_buildings_df['Qcs_sys_MWhyr'].sum() / \
                                                                cea_result_total_demand_buildings_df['GFA_m2'].sum() * 1000
        analysis_results_dict['EUI - heating demand [kWh/m2/yr]'] = cea_result_total_demand_buildings_df['QH_sys_MWhyr'].sum() / \
                                                          cea_result_total_demand_buildings_df['GFA_m2'].sum() * 1000
        analysis_results_dict['EUI - space heating demand [kWh/m2/yr]'] = cea_result_total_demand_buildings_df['Qhs_MWhyr'].sum() / \
                                                                cea_result_total_demand_buildings_df['GFA_m2'].sum() * 1000
        analysis_results_dict['EUI - domestic hot water demand [kWh/m2/yr]'] = cea_result_total_demand_buildings_df['Qww_MWhyr'].sum() / \
                                                                     cea_result_total_demand_buildings_df[
                                                                         'GFA_m2'].sum() * 1000

    except FileNotFoundError:
        analysis_results_dict['EUI - grid electricity [kWh/m2/yr]'] = na
        analysis_results_dict['EUI - enduse electricity [kWh/m2/yr]'] = na
        analysis_results_dict['EUI - cooling demand [kWh/m2/yr]'] = na
        analysis_results_dict['EUI - space cooling demand [kWh/m2/yr]'] = na
        analysis_results_dict['EUI - heating demand [kWh/m2/yr]'] = na
        analysis_results_dict['EUI - space heating demand [kWh/m2/yr]'] = na
        analysis_results_dict['EUI - domestic hot water demand [kWh/m2/yr]'] = na

        pv_database_path = os.path.join(cea_scenario, 'inputs/technology/components/CONVERSION.xlsx')
        pv_database_df = pd.read_excel(pv_database_path, sheet_name="PHOTOVOLTAIC_PANELS")
        panel_types = list(set(pv_database_df['code']))
        for panel_type in panel_types:
            analysis_results_dict[f'PV_{panel_type}_energy_penetration[-]'] = na
            analysis_results_dict[f'PV_{panel_type}_self_consumption[-]'] = na
            analysis_results_dict[f'PV_{panel_type}_energy_sufficiency[-]'] = na

    try:

        # metrics for on-site solar energy use
        pv_database_path = os.path.join(cea_scenario, 'inputs/technology/components/CONVERSION.xlsx')
        pv_database_df = pd.read_excel(pv_database_path, sheet_name="PHOTOVOLTAIC_PANELS")
        panel_types = list(set(pv_database_df['code']))
        for panel_type in panel_types:
            try:
                demand_buildings_path = os.path.join(cea_scenario, 'outputs/data/demand/Total_demand.csv')
                cea_result_total_demand_buildings_df = pd.read_csv(demand_buildings_path)
                pv_buildings_path = os.path.join(cea_scenario,
                                                 f'outputs/data/potentials/solar/PV_{panel_type}_total_buildings.csv')
                cea_result_pv_buildings_df = pd.read_csv(pv_buildings_path)
                analysis_results_dict[f'PV_{panel_type}_energy_penetration[-]'] = cea_result_pv_buildings_df['E_PV_gen_kWh'].sum() / (
                            cea_result_total_demand_buildings_df['GRID_MWhyr'].sum() * 1000)

            except FileNotFoundError:
                analysis_results_dict[f'PV_{panel_type}_energy_penetration[-]'] = na

            pv_hourly_path = os.path.join(cea_scenario,
                                          f'outputs/data/potentials/solar/PV_{panel_type}_total.csv')

            for time_period in time_period_options_autarky:
                try:
                    cea_result_pv_hourly_df = pd.read_csv(pv_hourly_path)
                    analysis_results_dict[f'PV_{panel_type}_self_consumption_{time_period}[-]'] = calc_self_consumption(
                        cea_result_pv_hourly_df['E_PV_gen_kWh'],
                        cea_result_demand_hourly_df['district_GRID_kWh'],
                        time_period=time_period)
                    analysis_results_dict[f'PV_{panel_type}_self_sufficiency_{time_period}[-]'] = calc_self_sufficiency(
                        cea_result_pv_hourly_df['E_PV_gen_kWh'],
                        cea_result_demand_hourly_df['district_GRID_kWh'],
                        time_period=time_period)
                except FileNotFoundError:
                    analysis_results_dict[f'PV_{panel_type}_self_consumption_{time_period}[-]'] = na
                    analysis_results_dict[f'PV_{panel_type}_energy_sufficiency_{time_period}[-]'] = na


    except FileNotFoundError:
        pass

    # metrics for capacity related normalisation and specific yield
    pv_database_path = os.path.join(cea_scenario, 'inputs/technology/components/CONVERSION.xlsx')
    pv_database_df = pd.read_excel(pv_database_path, sheet_name="PHOTOVOLTAIC_PANELS")
    panel_types = list(set(pv_database_df['code']))

    for panel_type in panel_types:
        module = pv_database_df[pv_database_df["code"] == panel_type].iloc[0]
        module_capacity_kWp = module["capacity_Wp"] / 1000
        module_area_m2 = module["module_area_m2"]

        pv_path = os.path.join(cea_scenario, f'outputs/data/potentials/solar/PV_{panel_type}_total_buildings.csv')

        try:
            cea_result_df = pd.read_csv(pv_path)
            system_area_m2 = cea_result_df['Area_PV_m2']
            max_kw = (module_capacity_kWp / module_area_m2) * system_area_m2
            analysis_results_dict[f'PV_{panel_type}_capacity_factor[-]'] = calc_capacity_factor(cea_result_df['E_PV_gen_kWh'],
                                                                                      max_kw)

        except FileNotFoundError:
            analysis_results_dict[f'PV_{panel_type}_capacity_factor[-]'] = na

        pv_hourly_path = os.path.join(cea_scenario,
                                      f'outputs/data/potentials/solar/PV_{panel_type}_total.csv')
        for time_period in time_period_options_yield:
            try:
                cea_result_df = pd.read_csv(pv_path)
                system_area_m2 = cea_result_df['Area_PV_m2']
                cea_result_pv_hourly_df = pd.read_csv(pv_hourly_path)

                # capacity_kWp
                max_kw = (module_capacity_kWp / module_area_m2) * system_area_m2

                analysis_results_dict[f'PV_{panel_type}_specific_yield_{time_period}[-]'] = calc_specific_yield(
                    cea_result_pv_hourly_df['E_PV_gen_kWh'],
                    max_kw,
                    time_period=time_period)
            except FileNotFoundError:
                analysis_results_dict[f'PV_{panel_type}_specific_yield_{time_period}[-]'] = na
    # metrics: pv impact
    pv_database_path = os.path.join(cea_scenario, 'inputs/technology/components/CONVERSION.xlsx')
    pv_database_df = pd.read_excel(pv_database_path, sheet_name="PHOTOVOLTAIC_PANELS")
    panel_types = list(set(pv_database_df['code']))

    for panel_type in panel_types:
        module = pv_database_df[pv_database_df["code"] == panel_type].iloc[0]
        module_impact_kgco2m2 = module["module_embodied_kgco2m2"]
        pv_totals_path = os.path.join(cea_scenario, f'outputs/data/potentials/solar/PV_{panel_type}_total_buildings.csv')

        try:
            cea_result_df = pd.read_csv(pv_totals_path)
            system_area_m2 = cea_result_df['Area_PV_m2'].sum()
            system_impact_kgco2 = module_impact_kgco2m2 * system_area_m2

            analysis_results_dict[f'PV_{panel_type}_system_emissions[kgCO2]'] = system_impact_kgco2
        except:
            analysis_results_dict[f'PV_{panel_type}_system_emissions[kgCO2]'] = na

    # metrics: pv generation intensity
    pv_database_path = os.path.join(cea_scenario, 'inputs/technology/components/CONVERSION.xlsx')
    pv_database_df = pd.read_excel(pv_database_path, sheet_name="PHOTOVOLTAIC_PANELS")
    panel_types = list(set(pv_database_df['code']))

    for panel_type in panel_types:
        # get module details
        module = pv_database_df[pv_database_df["code"] == panel_type].iloc[0]
        module_impact_kgco2m2 = module["module_embodied_kgco2m2"]
        module_lifetime_years = int(module["LT_yr"])


        pv_hourly_path = os.path.join(cea_scenario,
                                      f'outputs/data/potentials/solar/PV_{panel_type}_total.csv')

        for time_period in time_period_options_autarky:
            try:


                cea_result_pv_hourly_df = pd.read_csv(pv_hourly_path)

                analysis_results_dict[f'PV_{panel_type}_self_consumption_{time_period}[-]'] = calc_self_consumption(
                    cea_result_pv_hourly_df['E_PV_gen_kWh'],
                    cea_result_demand_hourly_df['district_GRID_kWh'],
                    time_period=time_period)
                analysis_results_dict[f'PV_{panel_type}_self_sufficiency_{time_period}[-]'] = calc_self_sufficiency(
                    cea_result_pv_hourly_df['E_PV_gen_kWh'],
                    cea_result_demand_hourly_df['district_GRID_kWh'],
                    time_period=time_period)

            except FileNotFoundError:
                analysis_results_dict[f'PV_{panel_type}_self_consumption_{time_period}[-]'] = na
                analysis_results_dict[f'PV_{panel_type}_energy_sufficiency_{time_period}[-]'] = na

        for time_period in time_period_options_generation_intensity:
            try:
                cea_result_df = pd.read_csv(pv_totals_path)
                system_area_m2 = cea_result_df['Area_PV_m2'].sum()
                system_impact_kgco2 = module_impact_kgco2m2 * system_area_m2

                cea_result_pv_hourly_df = pd.read_csv(pv_hourly_path)
                hourly_generation_kwh = cea_result_pv_hourly_df['E_PV_gen_kWh'].values
                lifetime_generation_kWh = projected_lifetime_output(hourly_generation_kwh, module_lifetime_years)
                module_generation_intensity_kgco2kwh = calc_generation_intensity(system_impact_kgco2,
                                                                                 lifetime_generation_kWh.sum(axis=0),
                                                                                 time_period=time_period)

                analysis_results_dict[
                    f'PV_{panel_type}_generation_intensity_{time_period}[kgco2kwh]'] = module_generation_intensity_kgco2kwh

            except FileNotFoundError:
                analysis_results_dict[f'PV_{panel_type}_self_consumption_{time_period}[-]'] = na
                analysis_results_dict[f'PV_{panel_type}_energy_sufficiency_{time_period}[-]'] = na

    # metrics: district heating plant - thermal
    try:
        dh_plant_thermal_path = os.path.join(cea_scenario, 'outputs/data/thermal-networkDH__plant_thermal_load_kW.csv')
        cea_result_df = pd.read_csv(dh_plant_thermal_path)
        analysis_results_dict['DH_plant_capacity_factor[-]'] = calc_capacity_factor(cea_result_df['thermal_load_kW'],
                                                                          cea_result_df['thermal_load_kW'].max())

    except FileNotFoundError:
        analysis_results_dict['DH_plant_capacity_factor[-]'] = na

    # metrics: district heating plant - pumping
    try:
        dh_plant_pumping_path = os.path.join(cea_scenario, 'outputs/data/thermal-networkDH__plant_pumping_load_kW.csv')
        cea_result_df = pd.read_csv(dh_plant_pumping_path)
        analysis_results_dict['DH_pump_capacity_factor[-]'] = calc_capacity_factor(cea_result_df['pressure_loss_total_kW'],
                                                                         cea_result_df['pressure_loss_total_kW'].max())

    except FileNotFoundError:
        analysis_results_dict['DH_pump_capacity_factor[-]'] = na

    # metrics: district cooling plant - thermal
    try:
        dc_plant_thermal_path = os.path.join(cea_scenario, 'outputs/data/thermal-network/DC__plant_thermal_load_kW.csv')
        cea_result_df = pd.read_csv(dc_plant_thermal_path)
        analysis_results_dict['DC_plant_capacity_factor[-]'] = calc_capacity_factor(cea_result_df['thermal_load_kW'],
                                                                          cea_result_df['thermal_load_kW'].max())

    except FileNotFoundError:
        analysis_results_dict['DC_plant_capacity_factor[-]'] = na

    # metrics: district cooling plant - pumping
    try:
        dc_plant_pumping_path = os.path.join(cea_scenario, 'outputs/data/thermal-network/DC__plant_pumping_load_kW.csv')
        cea_result_df = pd.read_csv(dc_plant_pumping_path)
        analysis_results_dict['DC_pump_capacity_factor[-]'] = calc_capacity_factor(cea_result_df['pressure_loss_total_kW'],
                                                                         cea_result_df['pressure_loss_total_kW'].max())

    except FileNotFoundError:
        analysis_results_dict['DC_pump_capacity_factor[-]'] = na

    # analysis_df = pd.DataFrame([cea_scenario], columns=['scenario_name'])
    # for k,v in analysis_results_dict.items():
    #     analysis_df[k] = v
    # # analysis_df = pd.DataFrame([cea_scenario], columns=['scenario_name'])
    # pd.Series()


    analysis_df = pd.DataFrame([analysis_results_dict])
    # return analysis DataFrame
    return analysis_df


def main(config):
    """
    Read through CEA results for all scenarios under a project and generate UBEM metrics for quick analysis.

    :param config: the configuration object to use
    :type config: cea.config.Configuration
    :return:
    """

    # Start the timer
    t0 = time.perf_counter()

    assert os.path.exists(config.general.project), 'input file not found: %s' % config.project

    project_path = config.general.project
    scenario_name = config.general.scenario_name
    project_boolean = config.result_reader_analysis.all_scenarios

    # deciding to run all scenarios or the current the scenario only
    if project_boolean:
        scenarios_list = os.listdir(project_path)
    else:
        scenarios_list = [scenario_name]

    # loop over one or all scenarios under the project
    analysis_project_df = pd.DataFrame()
    for scenario in scenarios_list:
        # Ignore hidden directories
        if scenario.startswith('.') or os.path.isfile(os.path.join(project_path, scenario)):
            continue

        cea_scenario = os.path.join(project_path, scenario)
        print(f'Reading and analysing the CEA results for Scenario {cea_scenario}.')
        # executing CEA commands
        analysis_scenario_df = exec_read_and_analyse(cea_scenario)
        analysis_scenario_df['scenario_name'] = scenario
        analysis_project_df = pd.concat([analysis_project_df, analysis_scenario_df])

    # write the results
    if project_boolean:
        analysis_project_path = os.path.join(config.general.project, 'result_analysis.csv')
        analysis_project_df.to_csv(analysis_project_path, index=False, float_format='%.2f')

    else:
        analysis_scenario_path = os.path.join(project_path, scenario_name,
                                              f'{scenario_name}_result_analysis.csv')
        analysis_project_df.to_csv(analysis_scenario_path, index=False, float_format='%.2f')

    # Print the time used for the entire processing
    time_elapsed = time.perf_counter() - t0
    print('The entire process of read-and-analyse is now completed - time elapsed: %d.2 seconds' % time_elapsed)


if __name__ == '__main__':
    main(cea.config.Configuration())
