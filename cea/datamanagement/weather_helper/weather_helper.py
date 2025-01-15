"""
The weather-helper script sets the weather data used (``inputs/weather.epw``) for simulations.
"""

import os
import shutil
from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import geopandas as gpd
import requests

import cea.config
import cea.inputlocator

__author__ = "Daren Thomas"
__copyright__ = "Copyright 2019, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Daren Thomas"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"

from cea.datamanagement.weather_helper.generate_weather_data_sources import WEATHER_DATA_LOCATION


def fetch_weather_data(weather_file: str, zone_file: str):
    """
    Fetch weather data from Climate.OneBuilding based on zone location

    """
    zone_gdf = gpd.read_file(zone_file)
    weather_data = gpd.read_file(WEATHER_DATA_LOCATION)

    # Find nearest weather data based on centroid of zone
    centroid = zone_gdf.dissolve().centroid.to_crs(weather_data.crs)[0]
    index = weather_data.sindex.nearest(centroid)[1][0]
    url = f"https://climate.onebuilding.org/{weather_data.iloc[index]['url']}"
    data_source_url = "https://climate.onebuilding.org/sources/default.html"

    print(f"Downloading weather data: {url}")
    r = requests.get(url)
    with TemporaryDirectory() as tmpdir, ZipFile(BytesIO(r.content)) as z:
        for file_info in z.infolist():
            if file_info.filename.endswith('.epw'):
                z.extract(file_info, tmpdir)
                shutil.copyfile(os.path.join(tmpdir, file_info.filename), weather_file)
    print(f"For more information about TMYx weather files, visit {data_source_url}")

    with open(os.path.join(os.path.dirname(weather_file), "reference.txt"), "w") as f:
        f.write(
            f"Weather file downloaded from {url}\n\n"
            f"Data source information: {data_source_url}"
        )


def copy_weather_file(source_weather_file, locator):
    """
    Copy a weather file to the scenario's inputs.

    :param string source_weather_file: path to a weather file (``*.epw``)
    :param cea.inputlocator.InputLocator locator: use the InputLocator to find output path
    :return: (this script doesn't return anything)
    """
    from shutil import copyfile
    assert os.path.exists(source_weather_file), "Could not find weather file: {source_weather_file}".format(
        source_weather_file=source_weather_file
    )
    copyfile(source_weather_file, locator.get_weather_file())
    print("Set weather for scenario <{scenario}> to {source_weather_file}".format(
        scenario=os.path.basename(locator.scenario),
        source_weather_file=source_weather_file
    ))

def parse_dat_weather_file(source_dat_file, output_epw_file):
    """
    convert a DWD .dat-file to a epw-file

    :param string source_dat_file: source .dat
    :param string output_epw_file: output EPW
    """
    import pandas as pd

    print(f"Parsing .dat file: {source_dat_file}")
    try:
        weather_data = pd.read_csv(source_dat_file, sep="\s+", skiprows=6, header=None)
        weather_data.columns = ['RW', 'HW', 'MM', 'DD', 'HH', 't', 'p', 'WR', 'WG', 'N', 'x', 'RF', 'B', 'D', 'A', 'E',
                                'IL']

        # from dat to epw
        with open(output_epw_file, 'w') as epw_file:
            epw_file.write("LOCATION,Weimar,-,DEU,SRC-TMYx,105550,50.983,11.317,1,268\n")
            epw_file.write("DESIGN CONDITIONS,0\n")
            epw_file.write("TYPICAL/EXTREME PERIODS,0\n")
            epw_file.write("GROUND TEMPERATURES,0\n")
            epw_file.write("HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0\n")
            epw_file.write("COMMENTS 1, converted from .dat to .epw by CEA\n")
            epw_file.write("COMMENTS 2\n")
            epw_file.write("DATA PERIODS,1,1,Data,Tuesday,1/1,12/31\n")

            for _, row in weather_data.iterrows():
                mm = int(row['MM'])
                dd = int(row['DD'])
                hh = int(row['HH'])
                epw_line = f"1958,{mm},{dd},{hh},60,B8E7B8B8?9?0?0?0?0?0?0B8B8B8B8?0?0F8F8A7E7, " \
                           f"{row['t']},99,99,{row['RF']}, {row['p']}, 9999, {row['A']}, {row['D']}, {row['B']}, {row['D']}," \
                           f"-9999, -9999, -9999, -9999,{row['WR']}, {row['WG']}, 99, 9999, 9999, 9999,0, 999999999,0," \
                           f" -999,-999,-999\n"
                epw_file.write(epw_line)
+    except pd.errors.EmptyDataError as e:
+        raise ValueError("The .dat file is empty or has incorrect format") from e
+    except pd.errors.ParserError as e:
+        raise ValueError("Failed to parse the .dat file - invalid format") from e
+    except Exception as e:
+        raise ValueError(f"Unexpected error while parsing .dat file: {str(e)}") from e

def main(config):
    """
    Assign the weather file to the input folder.

    :param cea.config.Configuration config: Configuration object for this script
    :return:
    """
    locator = cea.inputlocator.InputLocator(config.scenario)
    weather = config.weather_helper.weather

    if weather.endswith('.dat'):
        print(f"Detected .dat file: {weather}")
        # convert .dat in .epw
        dat_weather_file = weather
        epw_weather_file = locator.get_weather_file()
        parse_dat_weather_file(dat_weather_file, epw_weather_file)
    elif config.weather_helper.weather == 'climate.onebuilding.org':
        print("No weather provided, fetching from online sources.")
        fetch_weather_data(locator.get_weather_file(), locator.get_zone_geometry())
    else:
        copy_weather_file(weather, locator)


if __name__ == '__main__':
    main(cea.config.Configuration())
