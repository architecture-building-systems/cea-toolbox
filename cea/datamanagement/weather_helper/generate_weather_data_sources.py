import os

import geopandas as gpd
import pandas as pd

import fiona

fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

URL_LIST = [
    "https://climate.onebuilding.org/sources/Region1_Africa_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region2_Asia_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region2_Region6_Russia_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region3_South_America_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region4_USA_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region4_Canada_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region4_NA_CA_Caribbean_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region5_Southwest_Pacific_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region6_Europe_TMYx_EPW_Processing_locations.xlsx",
    "https://climate.onebuilding.org/sources/Region7_Antarctica_TMYx_EPW_Processing_locations.xlsx",
]

WEATHER_DATA_LOCATION = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'weather.geojson')

def main():
    # Combine for global data
    excels = [pd.read_excel(url) for url in URL_LIST]
    global_df = pd.concat(excels)

    # Filter for latest TMYx url
    latest_tmyx = global_df[global_df["URL"].str.contains("TMYx.2009-2023")].set_index("WMO")

    # Get second latest TMYx
    second_latest_tmyx = global_df[global_df["URL"].str.contains("TMYx.2007-2021")].set_index("WMO")
    diff_tmyx = second_latest_tmyx.loc[second_latest_tmyx.index.difference(latest_tmyx.index)]

    # Combine latest and diff TMYx
    combined_tmyx = pd.concat([latest_tmyx, diff_tmyx])
    combined_tmyx["url"] = combined_tmyx["URL"].str.extract(r'https?://climate.onebuilding.org/([^ ]+\.zip)')

    # Write to geojson
    gdf = gpd.GeoDataFrame(
        combined_tmyx,
        geometry=gpd.points_from_xy(combined_tmyx["Longitude (E+/W-)"], combined_tmyx["Latitude (N+/S-)"]),
        crs="EPSG:4326"
    )
    gdf[["url", "geometry"]].to_file(WEATHER_DATA_LOCATION, index=False)


if __name__ == '__main__':
    main()
