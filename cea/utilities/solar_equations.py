"""
solar equations
"""




import numpy as np
import pandas as pd
import ephem
import datetime
import collections
from math import radians, degrees, asin, sin, acos, cos, tan, atan, pi

from pyarrow import feather
from timezonefinder import TimezoneFinder
import pytz

__author__ = "Jimeno A. Fonseca"
__copyright__ = "Copyright 2015, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Jimeno A. Fonseca"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Daren Thomas"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"

from cea.utilities.date import get_date_range_hours_from_year


def _ephem_setup(latitude, longitude, altitude, pressure, temperature):
    # observer
    obs = ephem.Observer()
    obs.lat = str(latitude)
    obs.lon = str(longitude)
    obs.elevation = altitude
    obs.pressure = pressure / 100.
    obs.temp = temperature

    # sun
    sun = ephem.Sun()
    return obs, sun


def pyephem(datetime_local, latitude, longitude, altitude=0, pressure=101325,
            temperature=12):
    # Written by Will Holmgren (@wholmgren), University of Arizona, 2014

    try:
        datetime_utc = datetime_local.tz_convert('UTC')
    except ValueError:
        raise ('Unknown time zone from the case study.')

    sun_coords = pd.DataFrame(index=datetime_local)

    obs, sun = _ephem_setup(latitude, longitude, altitude,
                            pressure, temperature)

    # make and fill lists of the sun's altitude and azimuth
    # this is the pressure and temperature corrected apparent alt/az.
    alts = []
    azis = []
    for thetime in datetime_utc:
        obs.date = ephem.Date(thetime)
        sun.compute(obs)
        alts.append(sun.alt)
        azis.append(sun.az)

    sun_coords['apparent_elevation'] = alts
    sun_coords['apparent_azimuth'] = azis

    # redo it for p=0 to get no atmosphere alt/az
    obs.pressure = 0
    alts = []
    azis = []
    for thetime in datetime_utc:
        obs.date = ephem.Date(thetime)
        sun.compute(obs)
        alts.append(sun.alt)
        azis.append(sun.az)

    sun_coords['elevation'] = alts
    sun_coords['azimuth'] = azis

    # convert to degrees. add zenith
    sun_coords = np.rad2deg(sun_coords)
    sun_coords['apparent_zenith'] = 90 - sun_coords['apparent_elevation']
    sun_coords['zenith'] = 90 - sun_coords['elevation']

    return sun_coords


# solar properties
SunProperties = collections.namedtuple('SunProperties', ['g', 'Sz', 'Az', 'ha', 'trr_mean', 'worst_sh', 'worst_Az'])
def calc_datetime_local_from_weather_file(weather_data, latitude, longitude):
    # read date from the weather file
    year = weather_data['year'][0]
    datetime = get_date_range_hours_from_year(year)

    # get local time zone
    etc_timezone = get_local_etc_timezone(latitude, longitude)

    # convert to local time zone
    datetime_local = datetime.tz_localize(tz=etc_timezone)

    return datetime_local

def get_local_etc_timezone(latitude, longitude):
    '''
    This function gets the time zone at a given latitude and longitude in 'Etc/GMT' format.
    This time zone format is used in order to avoid issues caused by Daylight Saving Time (DST) (i.e., redundant or
    missing times in regions that use DST).
    However, note that 'Etc/GMT' uses a counter intuitive sign convention, where West of GMT is POSITIVE, not negative.
    So, for example, the time zone for Zurich will be returned as 'Etc/GMT-1'.

    :param latitude: Latitude at the project location
    :param longitude: Longitude at the project location
    '''

    # get the time zone at the given coordinates
    tf = TimezoneFinder()
    time = pytz.timezone(tf.timezone_at(lng=longitude, lat=latitude)).localize(
        datetime.datetime(2011, 1, 1)).strftime('%z')

    # invert sign and return in 'Etc/GMT' format
    if time[0] == '-':
        time_zone = 'Etc/GMT+' + time[2]
    else:
        time_zone = 'Etc/GMT-' + time[2]

    return time_zone

def calc_sun_properties(latitude, longitude, weather_data, datetime_local, config):
    solar_window_solstice = config.solar.solar_window_solstice
    hour_date = datetime_local.hour
    min_date = datetime_local.minute
    day_date = datetime_local.dayofyear
    worst_hour = calc_worst_hour(latitude, weather_data, solar_window_solstice)

    # solar elevation, azimuth and values for the 9-3pm period of no shading on the solar solstice
    sun_coords = pyephem(datetime_local, latitude, longitude)
    sun_coords['declination'] = np.vectorize(declination_degree)(day_date, 365)
    sun_coords['hour_angle'] = np.vectorize(get_hour_angle)(longitude, min_date, hour_date, day_date)
    worst_sh = sun_coords['elevation'].loc[datetime_local[worst_hour]]
    worst_Az = sun_coords['azimuth'].loc[datetime_local[worst_hour]]

    # mean transmissivity
    weather_data['diff'] = weather_data.difhorrad_Whm2 / weather_data.glohorrad_Whm2
    T_G_hour = weather_data[np.isfinite(weather_data['diff'])]
    T_G_day = np.round(T_G_hour.groupby(['dayofyear']).mean(numeric_only=True), 2)
    T_G_day['diff'] = T_G_day['diff'].replace(1, 0.90)
    transmittivity = (1 - T_G_day['diff']).mean()

    return SunProperties(g=sun_coords['declination'], Sz=sun_coords['zenith'], Az=sun_coords['azimuth'],
                         ha=sun_coords['hour_angle'], trr_mean=transmittivity, worst_sh=worst_sh, worst_Az=worst_Az)


def calc_sunrise(sunrise, Yearsimul, longitude, latitude):
    o, s = _ephem_setup(latitude, longitude, altitude=0, pressure=101325, temperature=12)
    for day in range(1, 366):  # Calculated according to NOAA website
        o.date = datetime.datetime(Yearsimul, 1, 1) + datetime.timedelta(day - 1)
        next_event = o.next_rising(s)
        sunrise[day - 1] = next_event.datetime().hour
    return sunrise


def declination_degree(day_date, TY):
    """The declination of the sun is the angle between Earth's equatorial plane and a line
    between the Earth and the sun. It varies between 23.45 degrees and -23.45 degrees,
    hitting zero on the equinoxes and peaking on the solstices. [1]_

    :param when: datetime.datetime, date/time for which to do the calculation
    :param TY: float, Total number of days in a year. eg. 365 days per year,(no leap days)
    :param DEC: float,  The declination of the Sun

    .. [1] http://pysolar.org/
    """

    return 23.45 * np.vectorize(sin)((2 * pi / (TY)) * (day_date - 81))


def get_hour_angle(longitude_deg, min_date, hour_date, day_date):
    solar_time = get_solar_time(longitude_deg, min_date, hour_date, day_date)
    return 15 * (12 - solar_time)


def get_solar_time(longitude_deg, min_date, hour_date, day_date):
    """
    returns solar time in hours for the specified longitude and time,
    accurate only to the nearest minute.
    longitude_deg
    min_date
    hour_date
    day_date
    """
    solar_time_min = hour_date * 60 + min_date + 4 * longitude_deg + get_equation_of_time(day_date)

    return solar_time_min / 60


def get_equation_of_time(day_date):
    B = (day_date - 1) * 360 / 365
    E = 229.2 * (0.000075 + 0.001868 * cos(B) - 0.032077 * sin(B) - 0.014615 * cos(2 * B) - 0.04089 * sin(2 * B))
    return E


# filter sensor points with low solar potential

def filter_low_potential(radiation_sensor_path, metadata_csv_path, config):
    """
    To filter the sensor points/hours with low radiation potential.

    #. keep sensors above min radiation
    #. eliminate points when hourly production < 50 W/m2
    #. augment the solar radiation due to differences between panel reflectance and original reflectances used in daysim

    :param radiation_sensor_path: solar insulation data on all surfaces of each building
    :type radiation_csv: str
    :param metadata_csv: solar insulation sensor data of each building
    :type metadata_csv: str
    :return max_annual_radiation: yearly horizontal radiation [Wh/m2/year]
    :rtype max_annual_radiation: float
    :return annual_radiation_threshold: minimum yearly radiation threshold for sensor selection [Wh/m2/year]
    :rtype annual_radiation_threshold: float
    :return sensors_rad_clean: radiation data of the filtered sensors [Wh/m2]
    :rtype sensors_rad_clean: dataframe
    :return sensors_metadata_clean: data of filtered sensor points measuring solar insulation of each building
    :rtype sensors_metadata_clean: dataframe

    Following assumptions are made:

    #. Sensor points with low yearly radiation are deleted. The threshold (minimum yearly radiation) is a percentage
       of global horizontal radiation. The percentage threshold (min_radiation) is a global variable defined by users.
    #. For each sensor point kept, the radiation value is set to zero when radiation value is below 50 W/m2.
    #. No solar panels on windows.
    """

    def f(x):
        # To filter the sensor points / hours with low radiation potential.
        if x <= 50:
            # eliminate points when hourly production < 50 W/m2
            return 0
        else:
            # keep sensors above min radiation
            return x

    # read radiation file
    sensors_rad = feather.read_feather(radiation_sensor_path)
    sensors_metadata = pd.read_csv(metadata_csv_path)

    # join total radiation to sensor_metadata
    sensors_rad_sum = sensors_rad.sum(0).to_frame('total_rad_Whm2')  # add new row with yearly radiation
    sensors_metadata.set_index('SURFACE', inplace=True)
    sensors_metadata = sensors_metadata.merge(sensors_rad_sum, left_index=True, right_index=True)  # [Wh/m2]

    # remove window surfaces
    sensors_metadata = sensors_metadata[sensors_metadata.TYPE != 'windows']

    # keep sensors if allow pv installation on walls or on roofs
    if config.solar.panel_on_roof is False:
        sensors_metadata = sensors_metadata[sensors_metadata.TYPE != 'roofs']
    if config.solar.panel_on_wall is False:
        sensors_metadata = sensors_metadata[sensors_metadata.TYPE != 'walls']


    # set min yearly radiation threshold for sensor selection
    # keep sensors above min production in sensors_rad
    max_annual_radiation = sensors_rad_sum.max().values[0]
    annual_radiation_threshold_Whperm2 = float(config.solar.annual_radiation_threshold)*1000
    sensors_metadata_clean = sensors_metadata[sensors_metadata.total_rad_Whm2 >= annual_radiation_threshold_Whperm2]
    sensors_rad_clean = sensors_rad[sensors_metadata_clean.index.tolist()]  # keep sensors above min radiation

    sensors_rad_clean = sensors_rad_clean.applymap(lambda x: f(x))

    return max_annual_radiation, annual_radiation_threshold_Whperm2, sensors_rad_clean, sensors_metadata_clean


# custom rooftop solar panel tilt angle

def calc_spacing_custom_angle(sensors_metadata_clean, solar_properties, max_rad_Whperm2yr, panel_properties,
                            panel_tilt_angle, roof_coverage):
    """
    This function first determines the row spacing and surface azimuth of panels at a custom tilt angle installed at
    each sensor point. Secondly, the installed PV module areas at each sensor point are calculated. Lastly, all the
    modules are categorized by their surface azimuth, tilt angle, and yearly radiation. The output will then be used to
    calculate the absorbed radiation.

    :param sensors_metadata_clean: data of filtered sensor points measuring solar insulation of each building
    :type sensors_metadata_clean: dataframe
    :param latitude: latitude of the case study location
    :type latitude: float
    :param solar_properties: A SunProperties, using worst_sh: solar elevation at the worst hour [degree], worst_Az: solar azimuth at the worst hour [degree]
                           and trr_mean: transmissivity / clearness index [-]
    :type solar_properties: cea.utilities.solar_equations.SunProperties
    :param module_length_m: length of the PV module [m]
    :type module_length_m: float
    :param max_rad_Whperm2yr: max radiation received on surfaces [Wh/m2/year]
    :type max_rad_Whperm2yr: float
    :param panel_properties: Properties of the PV/PVT/SC panels selected (from systems database)
    :type panel_properties: dict
    :param panel_tilt_angle: custom panel tilt angle to be used for the spacing calculation
    :type panel_tilt_angle: float
    :param roof_coverage: Maximum panel coverage of roof surfaces that reach minimum irradiation threshold. e.g., if 0.8 is selected, only 80% of the areas that reach the minimum irradiation threshold will be covered by PV.
    :type roof_coverage: float

    :returns sensors_metadata_clean: data of filtered sensor points categorized with module tilt angle, array spacing,
        surface azimuth, installed PV module area of each sensor point and the categories
    :rtype sensors_metadata_clean: dataframe

    Assumptions:

    #. Row spacing: Determine the row spacing by minimizing the shadow according to the solar elevation and azimuth at
       the worst hour of the year. The worst hour is a global variable defined by users.
    #. Surface azimuth (orientation) of panels: If the sensor is on a tilted roof, the orientation of the panel is the
        same as the roof. Sensors on flat roofs are all south facing.
    """

    # calculate panel tilt angle (B) for flat roofs (tilt < 5 degrees), slope roofs and walls.
    input_angle_rad = radians(panel_tilt_angle)
    sensors_metadata_clean['tilt_deg'] = np.vectorize(acos)(sensors_metadata_clean['Zdir'])  # surface tilt angle in rad
    sensors_metadata_clean['tilt_deg'] = np.vectorize(degrees)(sensors_metadata_clean['tilt_deg'])  # surface tilt angle in degrees
    sensors_metadata_clean['B_deg'] = np.where(sensors_metadata_clean['tilt_deg'] >= 5,
                                               sensors_metadata_clean['tilt_deg'],
                                               degrees(input_angle_rad))  # panel tilt angle in degrees

    # calculate spacing and surface azimuth of the panels for flat roofs
    module_length_m = panel_properties['module_length_m']
    optimal_spacing_flat_m = calc_optimal_spacing(solar_properties, input_angle_rad, module_length_m)
    sensors_metadata_clean['array_spacing_m'] = np.where(sensors_metadata_clean['tilt_deg'] >= 5, 0,
                                                         optimal_spacing_flat_m)
    sensors_metadata_clean['surface_azimuth_deg'] = np.vectorize(calc_surface_azimuth)(sensors_metadata_clean['Xdir'],
                                                                                       sensors_metadata_clean['Ydir'],
                                                                                       sensors_metadata_clean[
                                                                                           'B_deg'])  # degrees

    # calculate the surface area required to install one pv panel on flat roofs with defined tilt angle and array spacing
    if panel_properties['type'] == 'PV':
        module_width_m = module_length_m  # for PV
    else:
        module_width_m = panel_properties['module_area_m2'] / module_length_m  # for FP, ET
    module_flat_surface_area_m2 = module_width_m * (sensors_metadata_clean.array_spacing_m / 2 +
                                                    module_length_m * cos(input_angle_rad))
    area_per_module_m2 = module_width_m * module_length_m

    # calculate the pv/solar collector module area within the area of each sensor point
    sensors_metadata_clean['area_installed_module_m2'] = np.where(
        sensors_metadata_clean['tilt_deg'] >= 5, sensors_metadata_clean.AREA_m2,
        area_per_module_m2 * (roof_coverage * sensors_metadata_clean.AREA_m2 / module_flat_surface_area_m2))

    # categorize the sensors by surface_azimuth, B, GB
    result = np.vectorize(calc_categoriesroof)(sensors_metadata_clean.surface_azimuth_deg, sensors_metadata_clean.B_deg,
                                               sensors_metadata_clean.total_rad_Whm2, max_rad_Whperm2yr)
    sensors_metadata_clean['CATteta_z'] = result[0]
    sensors_metadata_clean['CATB'] = result[1]
    sensors_metadata_clean['CATGB'] = result[2]

    return sensors_metadata_clean

# optimal tilt angle and spacing of solar panels

def optimal_angle_and_tilt(sensors_metadata_clean, latitude, solar_properties, max_rad_Whperm2yr, panel_properties,
                           roof_coverage):
    """
    This function first determines the optimal tilt angle, row spacing and surface azimuth of panels installed at each
    sensor point. Secondly, the installed PV module areas at each sensor point are calculated. Lastly, all the modules
    are categorized with its surface azimuth, tilt angle, and yearly radiation. The output will then be used to
    calculate the absorbed radiation.

    :param sensors_metadata_clean: data of filtered sensor points measuring solar insulation of each building
    :type sensors_metadata_clean: dataframe
    :param latitude: latitude of the case study location
    :type latitude: float
    :param solar_properties: A SunProperties, using worst_sh: solar elevation at the worst hour [degree],
                                worst_Az: solar azimuth at the worst hour [degree]
                                and trr_mean: transmissivity / clearness index [-]
    :type solar_properties: cea.utilities.solar_equations.SunProperties
    :param module_length_m: length of the PV module [m]
    :type module_length_m: float
    :param max_rad_Whperm2yr: max radiation received on surfaces [Wh/m2/year]
    :type max_rad_Whperm2yr: float
    :param panel_properties: Properties of the PV/PVT/SC panels selected (from systems database)
    :type panel_properties: dict
    :param roof_coverage: Maximum panel coverage of roof surfaces that reach minimum irradiation threshold. e.g., if 0.8 is selected, only 80% of the areas that reach the minimum irradiation threshold will be covered by PV.
    :type roof_coverage: float

    :returns sensors_metadata_clean: data of filtered sensor points categorized with module tilt angle, array spacing,
        surface azimuth, installed PV module area of each sensor point and the categories
    :rtype sensors_metadata_clean: dataframe

    Assumptions:

    #. Tilt angle: If the sensor is on tilted roof, the panel will have the same tilt as the roof. If the sensor is on
       a wall, the tilt angle is 90 degree. Tilt angles for flat roof is determined using the method from Quinn et al.
    #. Row spacing: Determine the row spacing by minimizing the shadow according to the solar elevation and azimuth at
       the worst hour of the year. The worst hour is a global variable defined by users.
    #. Surface azimuth (orientation) of panels: If the sensor is on a tilted roof, the orientation of the panel is the
        same as the roof. Sensors on flat roofs are all south facing.
    """

    # calculate panel tilt angle (B) for flat roofs (tilt < 5 degrees), slope roofs and walls.
    optimal_angle_flat_rad = calc_optimal_angle(0, latitude, solar_properties.trr_mean)
        # assume panels face the equator (the results for surface azimuth = 0 or 180 are the same)
    sensors_metadata_clean['tilt_deg'] = np.vectorize(acos)(sensors_metadata_clean['Zdir'])  # surface tilt angle in rad
    sensors_metadata_clean['tilt_deg'] = np.vectorize(degrees)(
        sensors_metadata_clean['tilt_deg'])  # surface tilt angle in degrees
    sensors_metadata_clean['B_deg'] = np.where(sensors_metadata_clean['tilt_deg'] >= 5,
                                               sensors_metadata_clean['tilt_deg'],
                                               degrees(optimal_angle_flat_rad))  # panel tilt angle in degrees

    # calculate spacing and surface azimuth of the panels for flat roofs
    module_length_m = panel_properties['module_length_m']
    optimal_spacing_flat_m = calc_optimal_spacing(solar_properties, optimal_angle_flat_rad, module_length_m)
    sensors_metadata_clean['array_spacing_m'] = np.where(sensors_metadata_clean['tilt_deg'] >= 5, 0,
                                                         optimal_spacing_flat_m)
    sensors_metadata_clean['surface_azimuth_deg'] = np.vectorize(calc_surface_azimuth)(sensors_metadata_clean['Xdir'],
                                                                                       sensors_metadata_clean['Ydir'],
                                                                                       sensors_metadata_clean[
                                                                                           'B_deg'])  # degrees

    # calculate the surface area required to install one pv panel on flat roofs with defined tilt angle and array spacing
    if panel_properties['type'] == 'PV':
        module_width_m = module_length_m  # for PV
    else:
        module_width_m = panel_properties['module_area_m2'] / module_length_m  # for FP, ET
    module_flat_surface_area_m2 = module_width_m * (sensors_metadata_clean.array_spacing_m / 2 +
                                                    module_length_m * cos(optimal_angle_flat_rad))
    area_per_module_m2 = module_width_m * module_length_m

    # calculate the pv/solar collector module area within the area of each sensor point
    sensors_metadata_clean['area_installed_module_m2'] = np.where(sensors_metadata_clean['tilt_deg'] >= 5,
                                                                  sensors_metadata_clean.AREA_m2,
                                                                  roof_coverage * area_per_module_m2 *
                                                                  (sensors_metadata_clean.AREA_m2 /
                                                                   module_flat_surface_area_m2))

    # categorize the sensors by surface_azimuth, B, GB
    result = np.vectorize(calc_categoriesroof)(sensors_metadata_clean.surface_azimuth_deg, sensors_metadata_clean.B_deg,
                                               sensors_metadata_clean.total_rad_Whm2, max_rad_Whperm2yr)
    sensors_metadata_clean['CATteta_z'] = result[0]
    sensors_metadata_clean['CATB'] = result[1]
    sensors_metadata_clean['CATGB'] = result[2]

    return sensors_metadata_clean


def calc_optimal_angle(teta_z, latitude, transmissivity):
    """
    To calculate the optimal tilt angle of the solar panels.

    :param teta_z: surface azimuth, 0 degree south (east negative) or 0 degree north (east positive)
    :type teta_z: float
    :param latitude: latitude of the case study site
    :type latitude: float
    :param transmissivity: clearness index [-]
    :type transmissivity: float
    :return abs(b): optimal tilt angle [radians]
    :rtype abs(b): float

    ..[Quinn et al., 2013] S.W.Quinn, B.Lehman.A simple formula for estimating the optimum tilt angles of photovoltaic
    panels. 2013 IEEE 14th Work Control Model Electron, Jun, 2013, pp.1-8
    """
    if transmissivity <= 0.15:
        gKt = 0.977
    elif 0.15 < transmissivity <= 0.7:
        gKt = 1.237 - 1.361 * transmissivity
    else:
        gKt = 0.273
    Tad = 0.98  # transmittance-absorptance product of the diffuse radiation
    Tar = 0.97  # transmittance-absorptance product of the reflected radiation
    Pg = 0.2  # ground reflectance of 0.2
    l = radians(latitude)
    a = radians(teta_z)
    b = atan((cos(a) * tan(l)) * (1 / (1 + ((Tad * gKt - Tar * Pg) / (2 * (1 - gKt))))))  # eq.(11)
    return abs(b)


def calc_optimal_spacing(sun_properties, tilt_angle, module_length):
    """
    To calculate the optimal spacing between each panel to avoid shading.

    :param sun_properties: SunProperties, using worst_sh (Solar elevation at the worst hour [degree]) and worst_Az
                           (Solar Azimuth [degree] at the worst hour)
    :type sun_properties: SunProperties
    :param tilt_angle: optimal tilt angle for panels on flat surfaces [degree]
    :type tilt_angle: float
    :param module_length: [m]
    :type module_length: float
    :return D: optimal distance in [m]
    :rtype D: float
    """
    h = module_length * sin(tilt_angle)
    D1 = h / tan(radians(sun_properties.worst_sh))
    D = max(D1 * cos(radians(180 - sun_properties.worst_Az)), D1 * cos(radians(sun_properties.worst_Az - 180)))
    return D


def calc_categoriesroof(teta_z, B, GB, Max_Isol):
    """
    To categorize solar panels by the surface azimuth, tilt angle and yearly radiation.

    :param teta_z: surface azimuth [degree], 0 degree north (east positive, west negative)
    :type teta_z: float
    :param B: solar panel tile angle [degree]
    :type B: float
    :param GB: yearly radiation of sensors [Wh/m2/year]
    :type GB: float
    :param Max_Isol: maximum radiation received on surfaces [Wh/m2/year]
    :type Max_Isol: float
    :return CATteta_z: category of surface azimuth
    :rtype CATteta_z: float
    :return CATB: category of tilt angle
    :rtype CATB: float
    :return CATBG: category of yearly radiation
    :rtype CATBG: float
    """
    if -122.5 < teta_z <= -67:
        CATteta_z = 1
    elif -67 < teta_z <= -22.5:
        CATteta_z = 3
    elif -22.5 < teta_z <= 22.5:
        CATteta_z = 5
    elif 22.5 < teta_z <= 67:
        CATteta_z = 4
    elif 67 <= teta_z <= 122.5:
        CATteta_z = 2
    else:
        CATteta_z = 6
    B = degrees(B)
    if 0 <= B <= 5:
        CATB = 1  # flat roof
    elif 5 < B <= 15:
        CATB = 2  # tilted 5-15 degrees
    elif 15 < B <= 25:
        CATB = 3  # tilted 15-25 degrees
    elif 25 < B <= 40:
        CATB = 4  # tilted 25-40 degrees
    elif 40 < B <= 60:
        CATB = 5  # tilted 40-60 degrees
    elif B > 60:
        CATB = 6  # tilted >60 degrees
    else:
        CATB = None
        print('B not in expected range')

    GB_percent = GB / Max_Isol
    # if 0 < GB_percent <= 0.05:
    #     CATGB = 1
    # elif 0.05 < GB_percent <= 0.1:
    #     CATGB = 2
    # elif 0.1 < GB_percent <= 0.15:
    #     CATGB = 3
    # elif 0.15 < GB_percent <= 0.2:
    #     CATGB = 4
    # elif 0.2 < GB_percent <= 0.25:
    #     CATGB = 5
    # elif 0.25 < GB_percent <= 0.3:
    #     CATGB = 6
    # elif 0.3 < GB_percent <= 0.35:
    #     CATGB = 7
    # elif 0.35 < GB_percent <= 0.4:
    #     CATGB = 8
    # elif 0.4 < GB_percent<= 0.45:
    #     CATGB = 9
    # elif 0.45 < GB_percent <= 0.5:
    #     CATGB = 10
    # elif 0.5 < GB_percent <= 0.55:
    #     CATGB = 11
    # elif 0.55 < GB_percent <= 0.6:
    #     CATGB = 12
    # elif 0.6 < GB_percent <= 0.65:
    #     CATGB = 13
    # elif 0.65 < GB_percent <= 0.7:
    #     CATGB = 14
    # elif 0.7 < GB_percent <= 0.75:
    #     CATGB = 15
    # elif 0.75 < GB_percent <= 0.8:
    #     CATGB = 16
    # elif 0.8 < GB_percent <= 0.85:
    #     CATGB = 17
    # elif 0.85 < GB_percent <= 0.9:
    #     CATGB = 18
    # elif 0.9 < GB_percent <= 0.95:
    #     CATGB = 19
    # elif 0.95 < GB_percent <= 1:
    #     CATGB = 20
    # else:
    #     CATGB = None
    #     print('GB not in expected range')


    if 0 < GB_percent <= 0.1:
        CATGB = 1
    elif 0.1 < GB_percent <= 0.2:
        CATGB = 2
    elif 0.2 < GB_percent <= 0.3:
        CATGB = 3
    elif 0.3 < GB_percent <= 0.4:
        CATGB = 4
    elif 0.4 < GB_percent<= 0.5:
        CATGB = 5
    elif 0.5 < GB_percent <= 0.6:
        CATGB = 6
    elif 0.6 < GB_percent <= 0.7:
        CATGB = 7
    elif 0.7 < GB_percent <= 0.8:
        CATGB = 8
    elif 0.8 < GB_percent <= 0.9:
        CATGB = 9
    elif 0.90 < GB_percent <= 1:
        CATGB = 10
    else:
        CATGB = None
        print('GB not in expected range')

    return CATteta_z, CATB, CATGB


def calc_surface_azimuth(xdir, ydir, B):
    """
    Calculate surface azimuth from the surface normal vector (x,y,z) and tilt angle (B).
    Following the geological sign convention, an azimuth of 0 and 360 degree represents north, 90 degree is east.

    :param xdir: surface normal vector x in (x,y,z) representing east-west direction
    :param ydir: surface normal vector y in (x,y,z) representing north-south direction
    :param B: surface tilt angle in degree
    :type xdir: float
    :type ydir: float
    :type B: float
    :returns surface azimuth: the azimuth of the surface of a solar panel in degree
    :rtype surface_azimuth: float

    """
    B = radians(B)
    if B != 0:
        teta_z = degrees(asin(xdir / sin(B))) # surface azimuth before adjusting for sign convention
    else:
        # for flat panels, surface azimuth doesn't matter
        teta_z = 0
    # set the surface azimuth with on the sign convention (E,N)=(+,+)
    if xdir < 0:
        if ydir < 0:
            surface_azimuth = 180 + teta_z  # (xdir,ydir) = (-,-)
        else:
            surface_azimuth = 360 + teta_z  # (xdir,ydir) = (-,+)
    elif ydir < 0:
        surface_azimuth = 180 + teta_z  # (xdir,ydir) = (+,-)
    else:
        surface_azimuth = teta_z  # (xdir,ydir) = (+,+)
    return surface_azimuth  # degree


# calculate angle of incident

def calc_incident_angle_beam(g, lat, ha, tilt, teta_z):
    # calculate incident angle beam radiation
    part1 = sin(lat) * sin(g) * cos(tilt) - cos(lat) * sin(g) * sin(tilt) * cos(teta_z)
    part2 = cos(lat) * cos(g) * cos(ha) * cos(tilt) + sin(lat) * cos(g) * cos(ha) * sin(tilt) * cos(teta_z)
    part3 = cos(g) * sin(ha) * sin(tilt) * sin(teta_z)
    teta_B = acos(part1 + part2 + part3)
    return teta_B  # in radains


def calc_angle_of_incidence(g, lat, ha, tilt, teta_z):
    """
    To calculate angle of incidence from solar vector and surface normal vector.
    (Validated with Sandia pvlib.irrandiance.aoi)

    :param lat: latitude of the location of case study [radians]
    :param g: declination of the solar position [radians]
    :param ha: hour angle [radians]
    :param tilt: panel surface tilt angle [radians]
    :param teta_z: panel surface azimuth angle [radians]
    :type lat: float
    :type g: float
    :type ha: float
    :type tilt: float
    :type teta_z: float
    :return teta_B: angle of incidence [radians]
    :rtype teta_B: float

    .. [Sproul, A. B., 2017] Sproul, A.B. (2007). Derivation of the solar geometric relationships using vector analysis.
       Renewable Energy, 32(7), 1187-1205.
    """
    # surface normal vector
    n_E = sin(tilt) * sin(teta_z)
    n_N = sin(tilt) * cos(teta_z)
    n_Z = cos(tilt)
    # solar vector
    s_E = -cos(g) * sin(ha)
    s_N = sin(g) * cos(lat) - cos(g) * sin(lat) * cos(ha)
    s_Z = cos(g) * cos(lat) * cos(ha) + sin(g) * sin(lat)

    # angle of incidence
    teta_B = acos(n_E * s_E + n_N * s_N + n_Z * s_Z)
    return teta_B


# calculate sensor properties in each group

def calc_groups(radiation_of_sensors_clean, sensors_metadata_cat):
    """
    To calculate the mean hourly radiation of sensors in each group.

    :param radiation_of_sensors_clean: radiation data of the filtered sensors
    :type radiation_of_sensors_clean: dataframe
    :param sensors_metadata_cat: data of filtered sensor points categorized with module tilt angle, array spacing,
                                 surface azimuth, installed PV module area of each sensor point
    :type sensors_metadata_cat: dataframe
    :return number_groups: number of groups of sensor points
    :rtype number_groups: float
    :return hourlydata_groups: mean hourly radiation of sensors in each group
    :rtype hourlydata_groups: dataframe
    :return number_points: number of sensor points in each group
    :rtype number_points: array
    :return prop_observers: values of sensor properties of each group of sensors
    :rtype prop_observers: dataframe
    """

    # calculate number of groups as number of optimal combinations.
    sensors_metadata_cat['type_orientation'] = sensors_metadata_cat['TYPE'] + '_' + sensors_metadata_cat['orientation']
    sensors_metadata_cat['surface'] = sensors_metadata_cat.index
    sensor_groups_ob = sensors_metadata_cat.groupby(
        ['CATB', 'CATGB', 'CATteta_z', 'type_orientation'])  # group the sensors by categories
    number_groups = sensor_groups_ob.size().count() # TODO: check if redundant, it is actually equal to group_count
    group_keys = sensor_groups_ob.groups.keys()

    # empty dicts to store results
    group_properties = {}
    group_mean_radiations = {}
    number_points = {}
    group_count = 0
    for key in group_keys:
        # get surface names in group
        surfaces_in_group = sensor_groups_ob['surface'].groups[key].values
        number_points[group_count] = len(surfaces_in_group)
        # write group properties
        group_key = pd.Series({'CATB': key[0], 'CATGB': key[1], 'CATteta_z': key[2], 'type_orientation': key[3]})
        group_info = pd.Series({'number_srfs': number_points, 'srfs': (''.join(surfaces_in_group))})
        group_prop_sum = sensor_groups_ob.sum(numeric_only=True).loc[key][['AREA_m2', 'area_installed_module_m2']]
        group_prop_mean = sensor_groups_ob.mean(numeric_only=True).loc[key].drop(['area_installed_module_m2', 'AREA_m2'])
        group_properties[group_count] = pd.concat([group_key, group_prop_mean, group_prop_sum, group_info])
        # calculate mean radiation among surfaces in group
        group_mean_radiations[group_count] = radiation_of_sensors_clean[surfaces_in_group].mean(axis=1).values

        group_count += 1

    prop_observers = pd.DataFrame(group_properties).T
    hourlydata_groups = pd.DataFrame(group_mean_radiations)

    panel_groups = {'number_groups': number_groups, 'number_points': number_points,
                    'hourlydata_groups': hourlydata_groups, 'prop_observers': prop_observers}
    return panel_groups


# calculate the worst hour

def calc_worst_hour(latitude, weather_data, solar_window_solstice):
    """
    Calculate the first hour of solar window of the winter solstice for panel spacing.
    http://www.affordable-solar.com/learning-center/building-a-system/calculating-tilted-array-spacing/

    :param latitude: latitude of the site [degree]
    :type latitude: float
    :param weather_data: weather data of the site
    :type weather_data: pd.dataframe
    :param solar_window_solstice: the desired hour of shade-free solar window on the winter solstice.
    :type solar_window_solstice: floar
    :return worst_hour: the hour to calculate minimum spacing
    :rtype worst_hour: float


    """
    if latitude > 0:
        northern_solstice = weather_data.query('month == 12 & day == 21')
        worst_hour = northern_solstice[northern_solstice.hour == (12 - round(solar_window_solstice / 2))].index[0]
    else:
        southern_solstice = weather_data.query('month == 6 & day == 21')
        worst_hour = southern_solstice[southern_solstice.hour == (12 - round(solar_window_solstice / 2))].index[0]

    return worst_hour


def calc_radiation_type(group, hourly_radiation, weather_data):
    radiation_Wperm2 = pd.DataFrame({'I_sol': hourly_radiation[group]})
    radiation_Wperm2['I_diffuse'] = weather_data.ratio_diffhout * radiation_Wperm2.I_sol  # calculate diffuse radiation
    radiation_Wperm2['I_direct'] = radiation_Wperm2['I_sol'] - radiation_Wperm2[
        'I_diffuse']  # calculate direct radiation
    radiation_Wperm2.fillna(0, inplace=True)  # set nan to zero
    return radiation_Wperm2
