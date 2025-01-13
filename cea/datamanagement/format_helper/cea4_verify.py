"""
Verify the format of the input data for CEA-4 model.

"""

import os
import cea.config
import time
import geopandas as gpd
import pandas as pd


__author__ = "Zhongming Shi"
__copyright__ = "Copyright 2025, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Zhongming Shi"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"


SHAPEFILES = ['zone', 'surroundings']
COLUMNS_ZONE_4 = ['name', 'floors_bg', 'floors_ag', 'height_bg', 'height_ag',
                'year', 'const_type', 'use_type1', 'use_type1r', 'use_type2', 'use_type2r', 'use_type3', 'use_type3r']
COLUMNS_SURROUNDINGS_4 = ['name', 'height_ag', 'floors_ag']
CSV_BUILDING_PROPERTIES_4 = ['air_conditioning', 'architecture', 'indoor_comfort', 'internal_loads', 'supply_systems']
COLUMNS_AIR_CONDITIONING_4 = ['name',
                            'type_cs', 'type_hs', 'type_dhw', 'type_ctrl', 'type_vent',
                            'heat_starts', 'heat_ends', 'cool_starts', 'cool_ends']
COLUMNS_ARCHITECTURE_4 = ['name',
                        'Hs_ag', 'Hs_bg', 'Ns', 'Es', 'void_deck', 'wwr_north', 'wwr_west', 'wwr_east', 'wwr_south',
                        'type_cons', 'type_leak', 'type_floor', 'type_part', 'type_base', 'type_roof', 'type_wall',
                        'type_win', 'type_shade']
COLUMNS_INDOOR_COMFORT_4 = ['name',
                          'Tcs_set_C', 'Ths_set_C', 'Tcs_setb_C', 'Ths_setb_C', 'Ve_lsp', 'RH_min_pc', 'RH_max_pc']
COLUMNS_INTERNAL_LOADS_4 = ['name',
                          'Occ_m2p', 'Qs_Wp', 'X_ghp', 'Ea_Wm2', 'El_Wm2', 'Ed_Wm2', 'Ev_kWveh', 'Qcre_Wm2',
                          'Vww_ldp', 'Vw_ldp', 'Qhpro_Wm2', 'Qcpro_Wm2', 'Epro_Wm2']
COLUMNS_SUPPLY_SYSTEMS_4 = ['name',
                          'type_cs', 'type_hs', 'type_dhw', 'type_el']

## --------------------------------------------------------------------------------------------------------------------
## The paths to the input files for CEA-4
## --------------------------------------------------------------------------------------------------------------------

# The paths are relatively hardcoded for now without using the inputlocator script.
# This is because we want to iterate over all scenarios, which is currently not possible with the inputlocator script.
def path_to_input_file_without_db_4(scenario, item):

    if item == "zone":
        path_to_input_file = os.path.join(scenario, "inputs", "building-geometry", "zone.shp")
    elif item == "surroundings":
        path_to_input_file = os.path.join(scenario, "inputs", "building-geometry", "surroundings.shp")
    elif item == "air_conditioning":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "air_conditioning.csv")
    elif item == "architecture":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "architecture.csv")
    elif item == "indoor_comfort":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "indoor_comfort.csv")
    elif item == "internal_loads":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "internal_loads.csv")
    elif item == "supply_systems":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "supply_systems.csv")
    elif item == 'streets':
        path_to_input_file = os.path.join(scenario, "inputs", "networks", "streets.shp")
    elif item == 'terrain':
        path_to_input_file = os.path.join(scenario, "inputs", "topography", "terrain.tif")
    elif item == 'weather':
        path_to_input_file = os.path.join(scenario, "inputs", "weather", "weather.epw")
    else:
        raise ValueError(f"Unknown item {item}")

    return path_to_input_file


## --------------------------------------------------------------------------------------------------------------------
## Helper functions
## --------------------------------------------------------------------------------------------------------------------

def verify_shp(scenario, item, required_attributes):
    """
    Verify if a shapefile contains all required attributes.

    Parameters:
        scenario (str): Path or identifier for the scenario.
        item (str): Either "zone" or "surroundings".
        required_attributes (list): List of attribute names to verify.

    Returns:
        A list of missing attributes, or an empty list if all attributes are present.
    """
    # Construct the shapefile path
    shapefile_path = path_to_input_file_without_db_4(scenario, item)

    # Check if the shapefile exists
    if not os.path.isfile(shapefile_path):
        raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")

    # Load the shapefile
    try:
        gdf = gpd.read_file(shapefile_path)
    except Exception as e:
        raise ValueError(f"Error reading shapefile: {e}")

    # Get the column names from the shapefile's attribute table
    shapefile_columns = gdf.columns.tolist()

    # Check for missing attributes
    missing_attributes = [attr for attr in required_attributes if attr not in shapefile_columns]

    return missing_attributes


def verify_csv_4(scenario, item, required_columns):
    """
    Verify if a CSV file contains all required columns.

    Parameters:
        scenario (str): Path or identifier for the scenario.
        item (str): Identifier for the CSV file.
        required_columns (list): List of column names to verify.

    Returns:
        A list of missing columns, or an empty list if all columns are present.
    """
    # Construct the CSV file path
    csv_path = path_to_input_file_without_db_4(scenario, item)

    # Check if the CSV file exists
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Load the CSV file
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise ValueError(f"Error reading CSV file: {e}")

    # Get the column names from the CSV file
    csv_columns = df.columns.tolist()

    # Check for missing columns
    missing_columns = [col for col in required_columns if col not in csv_columns]

    return missing_columns


def verify_file_exists_4(scenario, items):
    """
    Verify if the files in the provided list exist for a given scenario.

    Parameters:
        scenario (str): Path or identifier for the scenario.
        items (list): List of file identifiers to check.

    Returns:
        list: A list of missing file identifiers, or an empty list if all files exist.
    """
    list_missing_files = []
    for file in items:
        path = path_to_input_file_without_db_4(scenario, file)
        if not os.path.isfile(path):
            list_missing_files.append(file)
    return list_missing_files


def verify_name_duplicates_4(scenario, item):
    """
    Verify if there are duplicate names in the 'name' column of a .csv or .shp file.

    Parameters:
        file_path (str): Path to the input file (either .csv or .shp).

    Returns:
        list: A list of duplicate names, or an empty list if no duplicates are found.
    """
    # Construct the CSV file path
    file_path = path_to_input_file_without_db_4(scenario, item)

    # Check file type and load as a DataFrame
    if file_path.endswith('.csv'):
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            raise ValueError(f"Error reading CSV file: {e}")
    elif file_path.endswith('.shp'):
        try:
            df = gpd.read_file(file_path)
        except Exception as e:
            raise ValueError(f"Error reading shapefile: {e}")
    else:
        raise ValueError("Unsupported file type. Please provide a .csv or .shp file.")

    # Find duplicate names
    list_names_duplicated = df['name'][df['name'].duplicated()].tolist()

    return list_names_duplicated


def print_verification_results_4(scenario_name, dict_missing):

    if all(not value for value in dict_missing.values()):
        print("✓" * 3)
        print('All inputs are verified as present and compatible with the current version of CEA-4 for Scenario: {scenario}, including:'.format(scenario=scenario_name),
              'input building-geometries ShapeFiles: [zone and surroundings], '
              'input building-properties .csv files: {csv_building_properties}.'.format(csv_building_properties=CSV_BUILDING_PROPERTIES_4)
              )
    else:
        print("!" * 3)
        print('All or some of input data files/columns are missing or incompatible with the current version of CEA-4 for Scenario: {scenario}. '.format(scenario=scenario_name),
              'If you are migrating your input data from CEA-3 to CEA-4 format, set the toggle `migrate_from_cea_3` to `True` and run the script again. '
              'If you manually prepared the input data, check the log for missing files and/or incompatible columns. Modify your input data according to the log above.'
              )


def verify_csv_file(scenario, item, required_columns, print_results=False):
    """
    Verify a CSV file's columns and name uniqueness.

    Args:
        scenario: The scenario path
        item: The item name (e.g., 'air_conditioning')
        required_columns: List of required columns
        print_results: Whether to print verification results

    Returns:
        list: List of missing columns
    """
    list_missing_columns = verify_csv_4(scenario, item, required_columns)
    if list_missing_columns:
        if print_results:
            print(f'Ensure column(s) are present in the {item}.csv: {list_missing_columns}')
    else:
        if 'name' not in list_missing_columns:
            list_names_duplicated = verify_name_duplicates_4(scenario, item)
            if list_names_duplicated and print_results:
                print(f'Ensure name(s) are unique in {item}.csv: {list_names_duplicated} is duplicated.')
    return list_missing_columns

## --------------------------------------------------------------------------------------------------------------------
## Unique traits for the CEA-4 format
## --------------------------------------------------------------------------------------------------------------------

def cea4_verify(scenario, print_results=False):

    #1. about zone.shp and surroundings.shp
    list_missing_attributes_zone = []
    list_missing_attributes_surroundings = []
    list_missing_files_shp_building_geometry = verify_file_exists_4(scenario, SHAPEFILES)

    if 'zone' not in list_missing_files_shp_building_geometry:
        list_missing_attributes_zone = verify_shp(scenario, 'zone', COLUMNS_ZONE_4)
        if list_missing_attributes_zone:
            if print_results:
                print('Ensure attribute(s) are present in zone.shp: {missing_attributes_zone}'.format(missing_attributes_zone=list_missing_attributes_zone))
            if 'name' not in list_missing_attributes_zone:
                list_names_duplicated = verify_name_duplicates_4(scenario, 'zone')
                if list_names_duplicated:
                    if print_results:
                        print('Ensure name(s) are unique in zone.shp: {list_names_duplicated} is duplicated.'.format(list_names_duplicated=list_names_duplicated))
    if 'surroundings' not in list_missing_files_shp_building_geometry:
        list_missing_attributes_surroundings = verify_shp(scenario, 'surroundings', COLUMNS_SURROUNDINGS_4)
        if list_missing_attributes_surroundings:
            if print_results:
                print('Ensure attribute(s) are present in surroundings.shp: {missing_attributes_surroundings}'.format(missing_attributes_surroundings=list_missing_attributes_surroundings))
            if 'name' not in list_missing_attributes_surroundings:
                list_names_duplicated = verify_name_duplicates_4(scenario, 'surroundings')
                if list_names_duplicated:
                    if print_results:
                        print('Ensure name(s) are unique in surroundings.shp: {list_names_duplicated} is duplicated.'.format(list_names_duplicated=list_names_duplicated))

    #2. about .csv files under the "inputs/building-properties" folder
    list_missing_columns_air_conditioning = []
    list_missing_columns_architecture = []
    list_missing_columns_indoor_comfort = []
    list_missing_columns_internal_loads = []
    list_missing_columns_supply_systems = []

    list_missing_files_csv_building_properties = verify_file_exists_4(scenario, CSV_BUILDING_PROPERTIES_4)
    if list_missing_files_csv_building_properties:
        if print_results:
            print('Ensure .csv file(s) are present in the building-properties folder: {missing_files_csv_building_properties}'.format(missing_files_csv_building_properties=list_missing_files_csv_building_properties))

    for item, columns in [
        ('air_conditioning', COLUMNS_AIR_CONDITIONING_4),
        ('architecture', COLUMNS_ARCHITECTURE_4),
        ('indoor_comfort', COLUMNS_INDOOR_COMFORT_4),
        ('internal_loads', COLUMNS_INTERNAL_LOADS_4),
        ('supply_systems', COLUMNS_SUPPLY_SYSTEMS_4)
    ]:
        if item not in list_missing_files_csv_building_properties:
            locals()[f'list_missing_columns_{item}'] = verify_csv_file(
                scenario, item, columns, print_results=print_results
            )
    #3. verify if terrain.tif, weather.epw and streets.shp exist
    list_missing_files_terrain = verify_file_exists_4(scenario, ['terrain'])
    if list_missing_files_terrain:
        if print_results:
            print('Ensure terrain.tif are present in the typography folder. Consider running Terrain Helper under Data Management.')

    list_missing_files_weather = verify_file_exists_4(scenario, ['weather'])
    if list_missing_files_weather:
        if print_results:
            print('Ensure weather.epw are present in the typography folder. Consider running Weather Helper under Data Management.')

    list_missing_files_streets = verify_file_exists_4(scenario, ['streets'])
    if list_missing_files_streets:
        if print_results:
            print('Ensure streets.shp are present in the typography folder. Consider running Streets Helper under Data Management, if Thermal-Networks analysis is required.')

    #4. verify the DB under the "inputs/technology/" folder
    list_missing_files_db = []

    # Compile the results
    dict_missing = {
        'building-geometry': list_missing_files_shp_building_geometry,
        'zone': list_missing_attributes_zone,
        'surroundings': list_missing_attributes_surroundings,
        'building-properties': list_missing_files_csv_building_properties,
        'air_conditioning': list_missing_columns_air_conditioning,
        'architecture': list_missing_columns_architecture,
        'indoor_comfort': list_missing_columns_indoor_comfort,
        'internal_loads': list_missing_columns_internal_loads,
        'supply_systems': list_missing_columns_supply_systems,
        'terrain': list_missing_files_terrain,
        'weather': list_missing_files_weather,
        'streets': list_missing_files_streets,
        'db': list_missing_files_db
    }

    # Print: End
    if print_results:
        print("-" * 60)

    return dict_missing


## --------------------------------------------------------------------------------------------------------------------
## Main function
## --------------------------------------------------------------------------------------------------------------------


def main(config):
    # Start the timer
    t0 = time.perf_counter()
    assert os.path.exists(config.general.project), 'input file not found: %s' % config.project

    # Get the scenario name
    scenario = config.scenario
    scenario_name = os.path.basename(scenario)

    # Print: Start
    div_len = 47 - len(scenario_name)
    print('+' * 60)
    print("-" * 1 + ' Scenario: {scenario} '.format(scenario=scenario_name) + "-" * div_len)

    # Execute the verification
    dict_missing = cea4_verify(scenario, print_results=True)

    # Print the results
    print_verification_results_4(scenario_name, dict_missing)

    # Print the time used for the entire processing
    time_elapsed = time.perf_counter() - t0

    # Print: End
    # print("-" * 1 + ' Scenario: {scenario} - end '.format(scenario=scenario_name) + "-" * 50)
    print('+' * 60)
    print('The entire process of CEA-4 format verification is now completed - time elapsed: %.2f seconds' % time_elapsed)

if __name__ == '__main__':
    main(cea.config.Configuration())
