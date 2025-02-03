"""
Mirgate the format of the input data to CEA-4 format after verification.

"""


import os
import cea.config
import time
import pandas as pd
import geopandas as gpd



__author__ = "Zhongming Shi"
__copyright__ = "Copyright 2025, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Zhongming Shi"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"

from cea.datamanagement.format_helper.cea4_verify import cea4_verify, verify_shp, \
    COLUMNS_ZONE_4, print_verification_results_4, path_to_input_file_without_db_4
from cea.utilities.dbf import dbf_to_dataframe

COLUMNS_ZONE_3 = ['Name', 'floors_bg', 'floors_ag', 'height_bg', 'height_ag']
CSV_BUILDING_PROPERTIES_3 = ['air_conditioning', 'architecture', 'indoor_comfort', 'internal_loads', 'supply_systems', 'typology']

COLUMNS_TYPOLOGY_3 = ['Name', 'YEAR', 'STANDARD', '1ST_USE', '1ST_USE_R', '2ND_USE', '2ND_USE_R', '3RD_USE', '3RD_USE_R']
COLUMNS_SURROUNDINGS_3 = ['Name', 'height_ag', 'floors_ag']
COLUMNS_AIR_CONDITIONING_3 = ['Name',
                            'type_cs', 'type_hs', 'type_dhw', 'type_ctrl', 'type_vent',
                            'heat_starts', 'heat_ends', 'cool_starts', 'cool_ends']
COLUMNS_ARCHITECTURE_3 = ['Name',
                        'Hs_ag', 'Hs_bg', 'Ns', 'Es', 'void_deck', 'wwr_north', 'wwr_west', 'wwr_east', 'wwr_south',
                        'type_cons', 'type_leak', 'type_floor', 'type_part', 'type_base', 'type_roof', 'type_wall',
                        'type_win', 'type_shade']
COLUMNS_INDOOR_COMFORT_3 = ['Name',
                          'Tcs_set_C', 'Ths_set_C', 'Tcs_setb_C', 'Ths_setb_C', 'Ve_lsp', 'RH_min_pc', 'RH_max_pc']
COLUMNS_INTERNAL_LOADS_3 = ['Name',
                          'Occ_m2p', 'Qs_Wp', 'X_ghp', 'Ea_Wm2', 'El_Wm2', 'Ed_Wm2', 'Ev_kWveh', 'Qcre_Wm2',
                          'Vww_ldp', 'Vw_ldp', 'Qhpro_Wm2', 'Qcpro_Wm2', 'Epro_Wm2']
COLUMNS_SUPPLY_SYSTEMS_3 = ['Name',
                          'type_cs', 'type_hs', 'type_dhw', 'type_el']
columns_mapping_dict_name = {'Name': 'name'}
columns_mapping_dict_typology = {'YEAR': 'year',
                                 'STANDARD': 'const_type',
                                 '1ST_USE': 'use_type1',
                                 '1ST_USE_R': 'use_type1r',
                                 '2ND_USE': 'use_type2',
                                 '2ND_USE_R': 'use_type2r',
                                 '3RD_USE': 'use_type3',
                                 '3RD_USE_R': 'use_type3r'
                                 }
COLUMNS_ZONE_TYPOLOGY_3 = ['Name', 'STANDARD', 'YEAR', '1ST_USE', '1ST_USE_R', '2ND_USE', '2ND_USE_R', '3RD_USE', '3RD_USE_R']

## --------------------------------------------------------------------------------------------------------------------
## The paths to the input files for CEA-3
## --------------------------------------------------------------------------------------------------------------------

# The paths are relatively hardcoded for now without using the inputlocator script.
# This is because we want to iterate over all scenarios, which is currently not possible with the inputlocator script.
def path_to_input_file_without_db_3(scenario, item):

    if item == "zone":
        path_to_input_file = os.path.join(scenario, "inputs", "building-geometry", "zone.shp")
    elif item == "surroundings":
        path_to_input_file = os.path.join(scenario, "inputs", "building-geometry", "surroundings.shp")
    elif item == "air_conditioning":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "air_conditioning.dbf")
    elif item == "architecture":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "architecture.dbf")
    elif item == "indoor_comfort":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "indoor_comfort.dbf")
    elif item == "internal_loads":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "internal_loads.dbf")
    elif item == "supply_systems":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "supply_systems.dbf")
    elif item == "typology":
        path_to_input_file = os.path.join(scenario, "inputs", "building-properties", "typology.dbf")
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


def verify_name_duplicates_3(scenario, item):
    """
    Verify if there are duplicate names in the 'name' column of a .csv or .shp file.

    Parameters:
        file_path (str): Path to the input file (either .csv or .shp).

    Returns:
        list: A list of duplicate names, or an empty list if no duplicates are found.
    """
    # Construct the CSV file path
    file_path = path_to_input_file_without_db_3(scenario, item)

    # Check file type and load as a DataFrame
    if file_path.endswith('.dbf'):
        try:
            df = dbf_to_dataframe(file_path)
        except Exception as e:
            raise ValueError(f"Error reading DBF file: {e}")
    elif file_path.endswith('.shp'):
        try:
            df = gpd.read_file(file_path)
        except Exception as e:
            raise ValueError(f"Error reading shapefile: {e}")
    else:
        raise ValueError("Unsupported file type. Please provide a .csv or .shp file.")

    # Find duplicate names
    list_names_duplicated = df['Name'][df['Name'].duplicated()].tolist()

    return list_names_duplicated

def verify_dbf_3(scenario, item, required_columns):
    """
    Verify if a DBF file contains all required columns.

    Parameters:
        scenario (str): Path or identifier for the scenario.
        item (str): Identifier for the CSV file.
        required_columns (list): List of column names to verify.

    Returns:
        A list of missing columns, or an empty list if all columns are present.
    """
    # Construct the CSV file path
    dbf_path = path_to_input_file_without_db_3(scenario, item)

    # Check if the CSV file exists
    if not os.path.isfile(dbf_path):
        raise FileNotFoundError(f"CSV file not found: {dbf_path}")

    # Load the CSV file
    try:
        df = dbf_to_dataframe(dbf_path)
    except Exception as e:
        raise ValueError(f"Error reading CSV file: {e}")

    # Get the column names from the CSV file
    dbf_columns = df.columns.tolist()

    # Check for missing columns
    missing_columns = [col for col in required_columns if col not in dbf_columns]

    return missing_columns


def replace_shapefile_dbf(scenario, item, new_dataframe, list_attributes_3):
    """
    Replace the DBF file of a shapefile with the contents of a new DataFrame,
    ensuring matching of `['Name']` in the shapefile and `['name']` in the new DataFrame.

    :param shapefile_path: Path to the shapefile (without file extension).
    :param new_dataframe: pandas DataFrame with the new data to replace the DBF file.
    """
    # Load the original shapefile
    shapefile_path = path_to_input_file_without_db_3(scenario, item)
    gdf = gpd.read_file(shapefile_path)

    # Convert the DataFrame to a GeoDataFrame
    new_gdf = gpd.GeoDataFrame(new_dataframe, geometry=gdf['geometry'], crs=gdf.crs)  # Replace CRS with your specific CRS

    # Save the updated shapefile
    new_gdf.to_file(shapefile_path, driver="ESRI Shapefile")

def verify_file_exists_3(scenario, items):
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
        path = path_to_input_file_without_db_3(scenario, file)
        if not os.path.isfile(path):
            list_missing_files.append(file)
    return list_missing_files


def migrate_dbf_to_csv(scenario, item, required_columns, verbose=False):
    """
    Migrate a DBF file to CSV format with column renaming.

    Args:
        scenario: The scenario path
        item: The item name (e.g., 'air_conditioning')
        required_columns: List of required columns
    """
    list_missing_columns = verify_dbf_3(scenario, item, required_columns)
    if list_missing_columns:
        print(f'! Ensure column(s) are present in the {item}.dbf: {list_missing_columns}')
    else:
        if 'Name' not in list_missing_columns:
            list_names_duplicated = verify_name_duplicates_3(scenario, item)
            if list_names_duplicated:
                print(f'! Ensure name(s) are unique in {item}.dbf: {list_names_duplicated} is duplicated.')
            else:
                df = dbf_to_dataframe(path_to_input_file_without_db_3(scenario, item))
                df.rename(columns=columns_mapping_dict_name, inplace=True)
                df.rename(columns=columns_mapping_dict_typology, inplace=True)
                df.to_csv(path_to_input_file_without_db_4(scenario, item), index=False)
                os.remove(path_to_input_file_without_db_3(scenario, item))
                if verbose:
                    print(f'- {item}.dbf has been migrated from CEA-3 to CEA-4 format.')

## --------------------------------------------------------------------------------------------------------------------
## Migrate to CEA-4 format from CEA-3 format
## --------------------------------------------------------------------------------------------------------------------

def migrate_cea3_to_cea4(scenario, verbose=False):

    #0. verify if everything is already in the correct format for CEA-4
    dict_missing = cea4_verify(scenario)
    if all(not value for value in dict_missing.values()):
        pass

    else:
        # Verify missing files for CEA-3 and CEA-4 formats
        list_missing_files_shp_building_geometry_4 = dict_missing.get('building-geometry')
        list_missing_files_dbf_building_properties_3 = verify_file_exists_3(scenario, CSV_BUILDING_PROPERTIES_3)
        list_missing_files_csv_building_properties_4 = dict_missing.get('building-properties')

        # Verify missing attributes/columns for CEA-4 format
        list_missing_attributes_zone_4 = dict_missing.get('zone')
        list_missing_attributes_surroundings_4 = dict_missing.get('surroundings')
        list_missing_columns_air_conditioning_4 = dict_missing.get('air_conditioning')
        list_missing_columns_architecture_4 = dict_missing.get('architecture')
        list_missing_columns_indoor_comfort_4 = dict_missing.get('indoor_comfort')
        list_missing_columns_internal_loads_4 = dict_missing.get('internal_loads')
        list_missing_columns_supply_systems_4 = dict_missing.get('supply_systems')

        #1. about zone.shp and surroundings.shp
        if 'zone' not in list_missing_files_shp_building_geometry_4:
            list_missing_attributes_zone_3 = verify_shp(scenario, 'zone', COLUMNS_ZONE_3)
            if not list_missing_attributes_zone_3 and list_missing_attributes_zone_4:
                # print('For Scenario: {scenario}, '.format(scenario=scenario_name), 'zone.shp follows the CEA-3 format.')
                zone_df_3 = gpd.read_file(path_to_input_file_without_db_3(scenario, 'zone'))
                zone_df_3.rename(columns=columns_mapping_dict_name, inplace=True)
                if 'typology' not in list_missing_files_dbf_building_properties_3:
                    list_missing_attributes_typology_3 = verify_dbf_3(scenario, 'typology', COLUMNS_TYPOLOGY_3)
                    if not list_missing_attributes_typology_3 and list_missing_attributes_zone_4:
                        # print('For Scenario: {scenario}, '.format(scenario=scenario_name), 'typology.shp follows the CEA-3 format.')
                        typology_df = dbf_to_dataframe(path_to_input_file_without_db_3(scenario, 'typology'))
                        typology_df = typology_df[COLUMNS_ZONE_TYPOLOGY_3]
                        typology_df.rename(columns=columns_mapping_dict_typology, inplace=True)
                        zone_df_4 = pd.merge(zone_df_3, typology_df, left_on=['name'], right_on=["Name"], how='left')
                        zone_df_4.drop(columns=['Name'], inplace=True)
                        zone_df_4 = zone_df_4[COLUMNS_ZONE_4]
                        replace_shapefile_dbf(scenario, 'zone', zone_df_4, COLUMNS_ZONE_3)
                        if verbose:
                            print('- zone.shp and typology.dbf have been merged and migrated to CEA-4 format.')
                    else:
                        raise ValueError('! typology.dbf exists but does not follow the CEA-3 format. CEA cannot proceed with the data migration. '
                                         'Check the following column(s) for CEA-3 format: {list_missing_attributes_typology_3}.'.format(list_missing_attributes_typology_3=list_missing_attributes_typology_3)
                                         )
                else:
                    print("! CEA is unable to produce a zone.shp compatible to CEA-4 format. To enable the migration, ensure typology.dbf (CEA-3 format) is present in building-properties folder.")

            elif list_missing_attributes_zone_3 and not list_missing_attributes_zone_4:
                pass
                # print('For Scenario: {scenario}, '.format(scenario=scenario_name), 'zone.shp already follows the CEA-4 format.')
            else:
                raise ValueError('! zone.shp exists but follows neither the CEA-3 nor CEA-4 format. CEA cannot proceed with the data migration.'
                                 'Check the following column(s) for CEA-3 format: {list_missing_attributes_zone_3}.'.format(list_missing_attributes_zone_3=list_missing_attributes_zone_3),
                                 'Check the following column(s) for CEA-4 format: {list_missing_attributes_zone_4}.'.format(list_missing_attributes_zone_4=list_missing_attributes_zone_4)
                                 )
        else:
            print("! Ensure zone.shp (CEA-3 format) is present in building-geometry folder.")

        if 'surroundings' not in list_missing_files_shp_building_geometry_4:
            list_missing_attributes_surroundings_3 = verify_shp(scenario, 'surroundings', COLUMNS_SURROUNDINGS_3)
            if not list_missing_attributes_surroundings_3 and list_missing_attributes_surroundings_4:
                # print('For Scenario: {scenario}, '.format(scenario=scenario_name), 'surroundings.shp follows the CEA-3 format.')
                surroundings_df = gpd.read_file(path_to_input_file_without_db_3(scenario, 'surroundings'))
                surroundings_df.rename(columns=columns_mapping_dict_name, inplace=True)
                replace_shapefile_dbf(scenario, 'surroundings', surroundings_df, COLUMNS_SURROUNDINGS_3)
                if verbose:
                    print('- surroundings.shp has been migrated from CEA-3 to CEA-4 format.')

            elif list_missing_attributes_surroundings_3 and not list_missing_attributes_surroundings_4:
                pass
                # print('For Scenario: {scenario}, '.format(scenario=scenario_name), 'surroundings.shp already follows the CEA-4 format.')
            else:
                raise ValueError('surroundings.shp exists but follows neither the CEA-3 nor CEA-4 format. CEA cannot proceed with the data migration.'
                                 'Check the following column(s) for CEA-3 format: {list_missing_attributes_surroundings_3}.'.format(list_missing_attributes_surroundings_3=list_missing_attributes_surroundings_3),
                                 'Check the following column(s) for CEA-4 format: {list_missing_attributes_surroundings_4}.'.format(list_missing_attributes_surroundings_4=list_missing_attributes_surroundings_4)
                                 )
        else:
            print('! (optional) Run Surroundings Helper to generate surroundings.shp after the data migration.')

        #2. about the .dbf files in the building-properties folder to be migrated to .csv files
        if 'air_conditioning' in list_missing_files_csv_building_properties_4 and not list_missing_columns_air_conditioning_4:
            if 'air_conditioning' not in list_missing_files_dbf_building_properties_3:
                migrate_dbf_to_csv(scenario, 'air_conditioning', COLUMNS_AIR_CONDITIONING_3, verbose=verbose)
            else:
                print("! Ensure either air_conditioning.dbf or air_conditioning.csv is present in building-properties folder. Run Archetypes-Helper to generate air_conditioning.csv.")
        elif 'air_conditioning' not in list_missing_files_csv_building_properties_4 and list_missing_columns_air_conditioning_4:
            print('! Ensure column(s) are present in air_conditioning.csv: {list_missing_columns_air_conditioning_4}.'.format(list_missing_columns_air_conditioning_4=list_missing_columns_air_conditioning_4))
        else:
            pass

        if 'architecture' in list_missing_files_csv_building_properties_4 and not list_missing_columns_architecture_4:
            if 'architecture' not in list_missing_files_dbf_building_properties_3:
                migrate_dbf_to_csv(scenario, 'architecture', COLUMNS_ARCHITECTURE_3, verbose=verbose)
            else:
                print("! Ensure either architecture.dbf or architecture.csv is present in building-properties folder. Run Archetypes-Helper to generate architecture.csv.")
        elif 'architecture' not in list_missing_files_csv_building_properties_4 and list_missing_columns_architecture_4:
            print('! Ensure column(s) are present in architecture.csv: {list_missing_columns_architecture_4}.'.format(list_missing_columns_architecture_4=list_missing_columns_architecture_4))
        else:
            pass

        if 'indoor_comfort' in list_missing_files_csv_building_properties_4 and not list_missing_columns_indoor_comfort_4:
            if 'indoor_comfort' not in list_missing_files_dbf_building_properties_3:
                migrate_dbf_to_csv(scenario, 'indoor_comfort', COLUMNS_INDOOR_COMFORT_3, verbose=verbose)
            else:
                print("! Ensure either indoor_comfort.dbf or indoor_comfort.csv is present in building-properties folder. Run Archetypes-Helper to generate indoor_comfort.csv.")
        elif 'indoor_comfort' not in list_missing_files_csv_building_properties_4 and list_missing_columns_indoor_comfort_4:
            print('! Ensure column(s) are present in indoor_comfort.csv: {list_missing_columns_indoor_comfort_4}.'.format(list_missing_columns_indoor_comfort_4=list_missing_columns_indoor_comfort_4))
        else:
            pass

        if 'internal_loads' in list_missing_files_csv_building_properties_4 and not list_missing_columns_internal_loads_4:
            if 'internal_loads' not in list_missing_files_dbf_building_properties_3:
                migrate_dbf_to_csv(scenario, 'internal_loads', COLUMNS_INTERNAL_LOADS_3, verbose=verbose)
            else:
                print("! Ensure either internal_loads.dbf or internal_loads.csv is present in building-properties folder. Run Archetypes-Helper to generate internal_loads.csv.")
        elif 'internal_loads' not in list_missing_files_csv_building_properties_4 and list_missing_columns_internal_loads_4:
            print('! Ensure column(s) are present in internal_loads.csv: {list_missing_columns_internal_loads_4}.'.format(list_missing_columns_internal_loads_4=list_missing_columns_internal_loads_4))
        else:
            pass

        if 'supply_systems' in list_missing_files_csv_building_properties_4 and not list_missing_columns_supply_systems_4:
            if 'supply_systems' not in list_missing_files_dbf_building_properties_3:
                migrate_dbf_to_csv(scenario, 'supply_systems', COLUMNS_SUPPLY_SYSTEMS_3, verbose=verbose)
            else:
                print("! Ensure either supply_systems.dbf or supply_systems.csv is present in building-properties folder. Run Archetypes-Helper to generate supply_systems.csv.")
        elif 'supply_systems' not in list_missing_files_csv_building_properties_4 and list_missing_columns_supply_systems_4:
            print('! Ensure column(s) are present in supply_systems.csv: {list_missing_columns_supply_system_4}.'.format(list_missing_columns_supply_system_4=list_missing_columns_supply_systems_4))
        else:
            pass

        if 'typology' not in list_missing_files_dbf_building_properties_3:
            typology_path = path_to_input_file_without_db_3(scenario, 'typology')
            if os.path.exists(typology_path):
                os.remove(typology_path)
                if verbose:
                    print('- typology.dbf has been removed as it is no longer needed by CEA-4.')


        # # Print: End
        # print('-' * 49)

## --------------------------------------------------------------------------------------------------------------------
## Main function
## --------------------------------------------------------------------------------------------------------------------


def main(config):
    # Start the timer
    t0 = time.perf_counter()
    assert os.path.exists(config.general.project), 'input file not found: %s' % config.project

    scenario = config.scenario
    scenario_name = os.path.basename(scenario)

    # Print: Start
    div_len = 37 - len(scenario_name)
    print('-' * 39)
    print("-" * 1 + ' Scenario: {scenario} '.format(scenario=scenario_name) + "-" * div_len)

    # Execute the verification
    migrate_cea3_to_cea4(scenario)

    # Execute the verification again
    dict_missing = cea4_verify(scenario)

    # Print the verification results
    print_verification_results_4(scenario_name, dict_missing)

    # Print: End
    # print("-" * 1 + ' Scenario: {scenario} - end '.format(scenario=scenario_name) + "-" * 50)
    print('+' * 104)

    # Print the time used for the entire processing
    time_elapsed = time.perf_counter() - t0
    print('The entire process of data migration from CEA-3 to CEA-4 is now completed - time elapsed: %.2f seconds' % time_elapsed)

if __name__ == '__main__':
    main(cea.config.Configuration())
