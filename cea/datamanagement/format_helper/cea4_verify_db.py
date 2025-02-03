"""
Verify the format of DB for CEA-4 model.

"""


import os
import cea.config
import time
import pandas as pd
import numpy as np
from cea.schemas import schemas
import re

__author__ = "Zhongming Shi"
__copyright__ = "Copyright 2025, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Zhongming Shi"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"


ARCHETYPES = ['CONSTRUCTION_TYPE', 'USE_TYPE']
SCHEDULES_FOLDER = ['SCHEDULES']
ENVELOPE_ASSEMBLIES = ['MASS', 'TIGHTNESS', 'FLOOR', 'WALL', 'WINDOW', 'SHADING', 'ROOF']
HVAC_ASSEMBLIES = ['HVAC_CONTROLLER', 'HVAC_HOT_WATER', 'HVAC_HEATING', 'HVAC_COOLING', 'HVAC_VENTILATION']
SUPPLY_ASSEMBLIES = ['SUPPLY_COOLING', 'SUPPLY_ELECTRICITY', 'SUPPLY_HEATING', 'SUPPLY_HOT_WATER']
CONVERSION_COMPONENTS = ['ABSORPTION_CHILLERS', 'BOILERS', 'BORE_HOLES', 'COGENERATION_PLANTS', 'COOLING_TOWERS',
                         'FUEL_CELLS', 'HEAT_EXCHANGERS', 'HEAT_PUMPS', 'HYDRAULIC_PUMPS', 'PHOTOVOLTAIC_PANELS',
                         'PHOTOVOLTAIC_THERMAL_PANELS', 'POWER_TRANSFORMERS', 'SOLAR_THERMAL_PANELS',
                         'THERMAL_ENERGY_STORAGES', 'UNITARY_AIR_CONDITIONERS', 'VAPOR_COMPRESSION_CHILLERS'
                         ]
DISTRIBUTION_COMPONENTS = ['THERMAL_GRID']
FEEDSTOCKS_COMPONENTS = ['BIOGAS', 'COAL', 'DRYBIOMASS', 'ENERGY_CARRIERS', 'GRID', 'HYDROGEN', 'NATURALGAS', 'OIL', 'SOLAR', 'WETBIOMASS', 'WOOD']
dict_assembly = {'MASS': 'envelope_type_mass', 'TIGHTNESS': 'envelope_type_leak', 'FLOOR': 'envelope_type_floor',
                 'WALL': 'envelope_type_wall', 'WINDOW': 'envelope_type_win', 'SHADING': 'envelope_type_shade',
                 'ROOF': 'envelope_type_roof', 'HVAC_CONTROLLER': 'hvac_type_ctrl', 'HVAC_HOT_WATER': 'hvac_type_dhw',
                 'HVAC_HEATING': 'hvac_type_hs', 'HVAC_COOLING': 'hvac_type_cs', 'HVAC_VENTILATION': 'hvac_type_vent',
                 'SUPPLY_COOLING': 'supply_type_cs', 'SUPPLY_ELECTRICITY': 'supply_type_el', 'SUPPLY_HEATING': 'supply_type_hs',
                 'SUPPLY_HOT_WATER': 'supply_type_dhw',
                 }
ASSEMBLIES_FOLDERS = ['ENVELOPE', 'HVAC', 'SUPPLY']
COMPONENTS_FOLDERS = ['CONVERSION', 'DISTRIBUTION', 'FEEDSTOCKS']
dict_ASSEMBLIES_COMPONENTS = {'ENVELOPE': ENVELOPE_ASSEMBLIES, 'HVAC': HVAC_ASSEMBLIES, 'SUPPLY': SUPPLY_ASSEMBLIES,
                              'CONVERSION': CONVERSION_COMPONENTS, 'DISTRIBUTION': DISTRIBUTION_COMPONENTS, 'FEEDSTOCKS': FEEDSTOCKS_COMPONENTS}
mapping_dict_db_item_to_schema_locator = {'CONSTRUCTION_TYPE': 'get_database_archetypes_construction_type',
                                          'USE_TYPE': 'get_database_archetypes_use_type',
                                          'SCHEDULES': 'get_database_archetypes_schedules',
                                          'CONSTRUCTION': 'get_database_assemblies_envelope_construction',
                                          'MASS': 'get_database_assemblies_envelope_mass',
                                          'FLOOR': 'get_database_assemblies_envelope_floor',
                                          'WALL': 'get_database_assemblies_envelope_wall',
                                          'WINDOW': 'get_database_assemblies_envelope_window',
                                          'SHADING': 'get_database_assemblies_envelope_shading',
                                          'ROOF': 'get_database_assemblies_envelope_roof',
                                          'TIGHTNESS': 'get_database_assemblies_envelope_tightness',
                                          'HVAC_CONTROLLER': 'get_database_assemblies_hvac_controller',
                                          'HVAC_COOLING': 'get_database_assemblies_hvac_cooling',
                                          'HVAC_HEATING': 'get_database_assemblies_hvac_heating',
                                          'HVAC_HOT_WATER': 'get_database_assemblies_hvac_hot_water',
                                          'HVAC_VENTILATION': 'get_database_assemblies_hvac_ventilation',
                                          'SUPPLY_COOLING': 'get_database_assemblies_supply_cooling',
                                          'SUPPLY_HEATING': 'get_database_assemblies_supply_heating',
                                          'SUPPLY_HOT_WATER': 'get_database_assemblies_supply_hot_water',
                                          'SUPPLY_ELECTRICITY': 'get_database_assemblies_supply_electricity',
                                          'ABSORPTION_CHILLERS': 'get_database_components_conversion_absorption_chillers',
                                          'BOILERS': 'get_database_components_conversion_boilers',
                                          'BORE_HOLES': 'get_database_components_conversion_bore_holes',
                                          'COGENERATION_PLANTS': 'get_database_components_conversion_cogeneration_plants',
                                          'COOLING_TOWERS': 'get_database_components_conversion_cooling_towers',
                                          'FUEL_CELLS': 'get_database_components_conversion_fuel_cells',
                                          'HEAT_EXCHANGERS': 'get_database_components_conversion_heat_exchangers',
                                          'HEAT_PUMPS': 'get_database_components_conversion_heat_pumps',
                                          'HYDRAULIC_PUMPS': 'get_database_components_conversion_hydraulic_pumps',
                                          'PHOTOVOLTAIC_PANELS': 'get_database_components_conversion_photovoltaic_panels',
                                          'PHOTOVOLTAIC_THERMAL_PANELS': 'get_database_components_conversion_photovoltaic_thermal_panels',
                                          'POWER_TRANSFORMERS': 'get_database_components_conversion_power_transformers',
                                          'SOLAR_THERMAL_PANELS': 'get_database_components_conversion_solar_thermal_panels',
                                          'THERMAL_ENERGY_STORAGES': 'get_database_components_conversion_thermal_energy_storages',
                                          'UNITARY_AIR_CONDITIONERS': 'get_database_components_conversion_unitary_air_conditioners',
                                          'VAPOR_COMPRESSION_CHILLERS': 'get_database_components_conversion_vapor_compression_chillers',
                                          'THERMAL_GRID': 'get_database_components_distribution_thermal_grid',
                                          'BIOGAS': 'get_database_components_feedstocks_biogas',
                                          'COAL': 'get_database_components_feedstocks_coal',
                                          'DRYBIOMASS': 'get_database_components_feedstocks_drybiomass',
                                          'ENERGY_CARRIERS': 'get_database_components_feedstocks_energy_carriers',
                                          'GRID': 'get_database_components_feedstocks_grid',
                                          'HYDROGEN': 'get_database_components_feedstocks_hydrogen',
                                          'NATURALGAS': 'get_database_components_feedstocks_naturalgas',
                                          'OIL': 'get_database_components_feedstocks_oil',
                                          'SOLAR': 'get_database_components_feedstocks_solar',
                                          'WETBIOMASS': 'get_database_components_feedstocks_wetbiomass',
                                          'WOOD': 'get_database_components_feedstocks_wood',
                                          }

mapping_dict_db_item_to_id_column = {'CONSTRUCTION_TYPE': 'const_type',
                                     'USE_TYPE':'use_type',
                                     'SCHEDULES': 'hour',
                                     'ENVELOPE': 'code',
                                     'HVAC': 'code',
                                     'SUPPLY': 'code',
                                     'CONVERSION': 'code',
                                     'DISTRIBUTION': 'code',
                                     'FEEDSTOCKS': 'hour',
                                     'ENERGY_CARRIERS': 'code',
                                     }

dict_code_to_name = {'CH':'VAPOR_COMPRESSION_CHILLERS',
                     'CT':'COOLING_TOWERS',
                     'HEX':'HEAT_EXCHANGERS',
                     'ACH':'ABSORPTION_CHILLERS',
                     'BO':'BOILERS',
                     'HP':'HEAT_PUMPS',
                     'BH':'BORE_HOLES',
                     'OEHR':'COGENERATION_PLANTS',
                     'FU':'COGENERATION_PLANTS',
                     'CCGT':'COGENERATION_PLANTS',
                     'FC':'FUEL_CELLS',
                     'PU':'HYDRAULIC_PUMPS',
                     'PV':'PHOTOVOLTAIC_PANELS',
                     'PVT':'PHOTOVOLTAIC_THERMAL_PANELS',
                     'TR':'POWER_TRANSFORMERS',
                     'SC': 'SOLAR_THERMAL_PANELS',
                     'TES':'THERMAL_ENERGY_STORAGES',
                     'AC':'UNITARY_AIR_CONDITIONERS',
                     }

## --------------------------------------------------------------------------------------------------------------------
## The paths to the input files for CEA-4
## --------------------------------------------------------------------------------------------------------------------

# The paths are relatively hardcoded for now without using the inputlocator script.
# This is because we want to iterate over all scenarios, which is currently not possible with the inputlocator script.
def path_to_db_file_4(scenario, item, sheet_name=None):

    if item == 'database':
        path_db_file = os.path.join(scenario, "inputs", "database")
    elif item == "CONSTRUCTION_TYPE":
        path_db_file = os.path.join(scenario, "inputs", "database", "ARCHETYPES", "CONSTRUCTION_TYPE.csv")
    elif item == "USE_TYPE":
        path_db_file = os.path.join(scenario, "inputs",  "database", "ARCHETYPES", "USE_TYPE.csv")
    elif item == "SCHEDULES":
        if sheet_name is None:
            path_db_file = os.path.join(scenario, "inputs", "database", "ARCHETYPES", "SCHEDULES")
        else:
            path_db_file = os.path.join(scenario, "inputs", "database", "ARCHETYPES", "SCHEDULES", "{use_type}.csv".format(use_type=sheet_name))
    elif item == "MONTHLY_MULTIPLIER":
        path_db_file = os.path.join(scenario, "inputs", "database", "ARCHETYPES", "SCHEDULES", "MONTHLY_MULTIPLIER.csv")
    elif item == "ENVELOPE":
        if sheet_name is None:
            path_db_file = os.path.join(scenario, "inputs",  "database", "ASSEMBLIES", "ENVELOPE")
        else:
            path_db_file = os.path.join(scenario, "inputs",  "database", "ASSEMBLIES", "ENVELOPE", "{envelope_assemblies}.csv".format(envelope_assemblies=sheet_name))
    elif item == "HVAC":
        if sheet_name is None:
            path_db_file = os.path.join(scenario, "inputs",  "database", "ASSEMBLIES", "HVAC")
        else:
            path_db_file = os.path.join(scenario, "inputs",  "database", "ASSEMBLIES", "HVAC", "{hvac_assemblies}.csv".format(hvac_assemblies=sheet_name))
    elif item == "SUPPLY":
        if sheet_name is None:
            path_db_file = os.path.join(scenario, "inputs",  "database", "ASSEMBLIES", "SUPPLY")
        else:
            path_db_file = os.path.join(scenario, "inputs",  "database", "ASSEMBLIES", "SUPPLY", "{supply_assemblies}.csv".format(supply_assemblies=sheet_name))
    elif item == "CONVERSION":
        if sheet_name is None:
            path_db_file = os.path.join(scenario, "inputs",  "database", "COMPONENTS", "CONVERSION")
        else:
            path_db_file = os.path.join(scenario, "inputs",  "database", "COMPONENTS", "CONVERSION", "{conversion_components}.csv".format(conversion_components=sheet_name))
    elif item == "DISTRIBUTION":
        if sheet_name is None:
            path_db_file = os.path.join(scenario, "inputs",  "database", "COMPONENTS", "DISTRIBUTION")
        else:
            path_db_file = os.path.join(scenario, "inputs",  "database", "COMPONENTS", "DISTRIBUTION", "{conversion_components}.csv".format(conversion_components=sheet_name))
    elif item == "FEEDSTOCKS":
        if sheet_name is None:
            path_db_file = os.path.join(scenario, "inputs",  "database", "COMPONENTS", "FEEDSTOCKS")
        else:
            path_db_file = os.path.join(scenario, "inputs",  "database", "COMPONENTS", "FEEDSTOCKS", "{feedstocks_components}.csv".format(feedstocks_components=sheet_name))
    else:
        raise ValueError(f"Unknown item {item}")

    return path_db_file


## --------------------------------------------------------------------------------------------------------------------
## Helper functions
## --------------------------------------------------------------------------------------------------------------------

def verify_file_against_schema_4_db(scenario, item, sheet_name=None):
    """
    Validate a file against a schema section in a YAML file.

    Parameters:
    - scenario (str): Path to the scenario.
    - item (str): Locator for the file to validate (e.g., 'get_zone_geometry').
    - self: Reference to the calling class/module.
    - verbose (bool, optional): If True, print validation errors to the console.

    Returns:
    - List[dict]: List of validation errors.
    """
    schema = schemas()

    # File path and schema section
    file_path = path_to_db_file_4(scenario, item, sheet_name)
    if sheet_name is None:
        locator = mapping_dict_db_item_to_schema_locator[item]
    elif sheet_name is not None and item == 'SCHEDULES':
        locator = mapping_dict_db_item_to_schema_locator[item]
    else:
        locator = mapping_dict_db_item_to_schema_locator[sheet_name]

    schema_section = schema[locator]
    schema_columns = schema_section['schema']['columns']
    if sheet_name == 'ENERGY_CARRIERS':
        id_column = mapping_dict_db_item_to_id_column[sheet_name]
    else:
        id_column = mapping_dict_db_item_to_id_column[item]

    # Determine file type and load the data
    if file_path.endswith('.csv'):
        try:
            df = pd.read_csv(file_path)
            col_attr = 'Column'
        except Exception as e:
            raise ValueError(f"Failed to read .csv file: {file_path}. Error: {e}")
    else:
        raise ValueError(f"Unsupported file type: {file_path}. Only .csv files are supported.")

    errors = []
    missing_columns = []

    # if id_column not in df.columns:
    #     if verbose:
    #         print(f"! CEA was not able to verify {os.path.basename(file_path)} "
    #               f"as a unique row identifier column such as (building) name or (component) code is not present.")

    # Validation process
    for col_name, col_specs in schema_columns.items():
        if col_name not in df.columns:
            missing_columns.append(col_name)
            continue

        if id_column not in missing_columns:

            col_data = df[col_name]

            # Check type
            if col_specs['type'] == 'string':
                invalid = ~col_data.apply(lambda x: isinstance(x, str) or pd.isnull(x))
            elif col_specs['type'] == 'int':
                invalid = ~col_data.apply(lambda x: isinstance(x, (int, np.integer)) or pd.isnull(x))
            elif col_specs['type'] == 'float':
                invalid = ~col_data.apply(lambda x: isinstance(x, (float, int, np.floating, np.integer)) or pd.isnull(x))
            else:
                invalid = pd.Series(False, index=col_data.index)  # Unknown types are skipped

            for idx in invalid[invalid].index:
                identifier = df.at[idx, id_column]
                errors.append({col_attr: col_name, "Issue": "Invalid type", "Row": identifier, "Value": col_data[idx]})
                errors.append(f"The {col_name} value for row {identifier} is invalid ({col_data[idx]}). Please check the data type.")

            # Check range
            if 'min' in col_specs:
                out_of_range = col_data[col_data < col_specs['min']]
                for idx, value in out_of_range.items():
                    identifier = df.at[idx, id_column]
                    errors.append(f"The {col_name} value for row {identifier} is too low ({value}). It should be at least {col_specs['min']}.")

            if 'max' in col_specs:
                out_of_range = col_data[col_data > col_specs['max']]
                for idx, value in out_of_range.items():
                    identifier = df.at[idx, id_column]
                    errors.append(f"The {col_name} value for row {identifier} is too high ({value}). It should be at most {col_specs['max']}.")


    # Relax from the descriptive columns which not used in the modelling
    missing_columns = [item for item in missing_columns if item not in ['geometry', 'reference', 'description', 'assumption']]

    return missing_columns, errors


def print_verification_results_4_db(scenario_name, dict_missing):

    if all(not value for value in dict_missing.values()):
        print("✓" * 3)
        print('All Database files/columns are verified as present and compatible with the current version of CEA-4 for Scenario: {scenario}.'.format(scenario=scenario_name),
              )
    else:
        print("!" * 3)
        print('All or some of Database files/columns are missing or incompatible with the current version of CEA-4 for Scenario: {scenario}. '.format(scenario=scenario_name))
        print('- If you are migrating your input data from CEA-3 to CEA-4 format, set the toggle `migrate_from_cea_3` to `True` for Feature CEA-4 Format Helper and click on Run. ')
        print('- If you manually prepared the Database, check the log for missing files and/or incompatible columns. Modify your Database accordingly. Otherwise, some or all CEA simulations will fail.')


def verify_file_exists_4_db(scenario, items, sheet_name=None):
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
        if sheet_name is None:
            path = path_to_db_file_4(scenario, file)
            if not os.path.isfile(path):
                list_missing_files.append(file)
        else:
            for sheet in sheet_name:
                path = path_to_db_file_4(scenario, file, sheet)
                if not os.path.isfile(path):
                    list_missing_files.append(sheet)
    return list_missing_files


def verify_assembly(scenario, ASSEMBLIES, list_missing_files_csv, verbose=False):
    list_existing_files_csv = list(set(dict_ASSEMBLIES_COMPONENTS[ASSEMBLIES]) - set(list_missing_files_csv))
    list_list_missing_columns_csv = []
    for assembly in list_existing_files_csv:
        list_missing_columns_csv, list_issues_against_csv = verify_file_against_schema_4_db(scenario, ASSEMBLIES, sheet_name=assembly)
        list_list_missing_columns_csv.append(list_missing_columns_csv)
        if verbose:
            if list_missing_columns_csv:
                print('! Ensure column(s) are present in {assembly}.csv: {missing_columns}.'.format(assembly=assembly, missing_columns=', '.join(map(str, list_missing_columns_csv))))
            if list_issues_against_csv:
                print('! Check values in {assembly}.csv:')
                print("\n".join(f"  {item}" for item in list_issues_against_csv))
    return list_list_missing_columns_csv

def get_csv_filenames(folder_path):
    """
    Get the names of all .csv files in the specified folder.

    Parameters:
    - folder_path (str): Path to the folder.

    Returns:
    - List[str]: A list of file names without path and without extension.
    """
    if not os.path.isdir(folder_path):
        raise ValueError(f"The provided path '{folder_path}' is not a valid directory.")

    # List all .csv files and remove the extension
    csv_filenames = [
        os.path.splitext(file)[0]  # Remove the file extension
        for file in os.listdir(folder_path)  # List files in the folder
        if file.endswith('.csv')  # Check for .csv extension
    ]

    return csv_filenames

def verify_components_exist(scenario, assemblies_item, list_assemblies_subset_items, list_assemblies_identifier_column_names, components_item, code_to_name=False):
    """
    Verify that all required components exist in the database and return missing components.

    Parameters:
    - scenario (str): Path to the scenario folder.
    - category (str): High-level category of the components (e.g., 'SUPPLY').
    - list_subset_items (list): Subsets of items to check for required components.
    - list_identifier_column_names (str): Column(s) used as unique identifiers for required components.
    - code_to_name (bool, optional): If True, convert codes to human-readable names. Default is False.

    Returns:
    - dict: Dictionary with merged values for duplicate keys.
        Keys are the names of missing components (if `code_to_name` is True).
        Values are the codes of missing components.
    """
    # Initialize lists to store codes and names
    required_codes = []
    provided_codes = []

    # Get the list of provided component names (e.g., from CSV files)
    provided_names = get_csv_filenames(path_to_db_file_4(scenario, components_item))

    if components_item == 'CONVERSION':
        # Collect codes from provided components
        for provided_name in provided_names:
            provided_df = pd.read_csv(path_to_db_file_4(scenario, components_item, provided_name))
            provided_codes.extend(np.unique(provided_df['code'].values).tolist())
    elif components_item == 'FEEDSTOCKS':
        provided_codes = provided_names

    # Collect codes from required components
    for subset_item in list_assemblies_subset_items:
        if subset_item not in verify_file_exists_4_db(scenario, [assemblies_item], dict_ASSEMBLIES_COMPONENTS[assemblies_item]):
            required_df = pd.read_csv(path_to_db_file_4(scenario, assemblies_item, subset_item))
            required_codes.extend(np.unique(required_df[list_assemblies_identifier_column_names].values).tolist())

    # Identify missing components
    missing_codes = list(set(required_codes) - set(provided_codes))
    missing_codes = [item for item in missing_codes if item not in ['NONE', '-']]

    # Convert codes to names if requested
    if code_to_name:
        missing_names = convert_code_to_name(missing_codes)
    else:
        missing_names = required_codes

    # Construct a dictionary with the merged values
    dict_merged = create_dict_merge_values(missing_names, missing_codes)
    return dict_merged


def verify_assemblies_exist(scenario, item, list_sheet_name, list_missing_columns_construction_type,archetypes='CONSTRUCTION_TYPE'):
    """
    Verify whether all required archetypes exist in the provided assemblies.

    Parameters:
    - scenario (str): Path to the scenario folder.
    - item (str): Item category (e.g., 'ASSEMBLIES').
    - list_sheet_name (list): List of sheet names to check.
    - archetypes (str): File name for archetypes (default: 'CONSTRUCTION_TYPE').

    Returns:
    - dict: A dictionary where keys are sheet names and values are lists of missing items.
    """
    list_list_missing_items = []
    list_missing_sheet_name = []

    for sheet_name in list_sheet_name:
        file_path_2 = path_to_db_file_4(scenario, item, sheet_name)
        file_path_1 = path_to_db_file_4(scenario, archetypes)
        column_name_2 = 'code'
        column_name_1 = dict_assembly[sheet_name]

        list_missing_items = []

        if column_name_1 not in list_missing_columns_construction_type:
            # Find missing items
            list_missing_items = find_missing_values_column_column(file_path_1, column_name_1, file_path_2, column_name_2)

        if list_missing_items:
            list_list_missing_items.append(list_missing_items)
            list_missing_sheet_name.append(sheet_name)

    # Merge missing items with corresponding sheet names
    dict_merged = create_dict_merge_values(list_missing_sheet_name, list_list_missing_items)

    return dict_merged


def find_missing_values_column_column(file_path_1, column_name_1, file_path_2, column_name_2):
    """
    Checks if all unique values in column_name_1 of the first CSV file are present in column_name_2 of the second CSV file.

    Parameters:
    - file_path_1 (str): Path to the first CSV file.
    - column_name_1 (str): Column name in the first CSV file to check.
    - file_path_2 (str): Path to the second CSV file.
    - column_name_2 (str): Column name in the second CSV file to check.

    Returns:
    - list: A list of missing items from column_name_1 that are not covered by column_name_2.
    """
    try:
        # Load both CSV files
        df1 = pd.read_csv(file_path_1)
        df2 = pd.read_csv(file_path_2)

        # Get unique values from both columns
        unique_values_1 = set(df1[column_name_1].dropna().unique())
        unique_values_2 = set(df2[column_name_2].dropna().unique())

        # Find missing items
        missing_items = list(unique_values_1 - unique_values_2)

        return missing_items
    except Exception as e:
        raise ValueError(f"An error occurred: {e}")


def find_missing_values_directory_column(directory_path_1, file_path_2, column_name_2):
    """
    Checks if all unique values in column_name_1 of the first CSV file are present in column_name_2 of the second CSV file.

    Parameters:
    - file_path_1 (str): Path to the first CSV file.
    - column_name_1 (str): Column name in the first CSV file to check.
    - file_path_2 (str): Path to the second CSV file.
    - column_name_2 (str): Column name in the second CSV file to check.

    Returns:
    - list: A list of missing items from column_name_1 that are not covered by column_name_2.
    """
    try:
        # Load both CSV files
        df2 = pd.read_csv(file_path_2)


        # Get unique values from both columns
        unique_values_1 = set(get_csv_filenames(directory_path_1))
        unique_values_2 = set(df2[column_name_2].dropna().unique())

        # Find missing items
        missing_items = list(unique_values_1 - unique_values_2)

        if 'ENERGY_CARRIERS' in missing_items:
            missing_items.remove('ENERGY_CARRIERS')
        if 'SOLAR' in missing_items:
            missing_items.remove('SOLAR')
        if 'MONTHLY_MULTIPLIER' in missing_items:
            missing_items.remove('MONTHLY_MULTIPLIER')

        return missing_items
    except Exception as e:
        raise ValueError(f"An error occurred: {e}")



def create_dict_merge_values(keys, values):
    """
    Create a dictionary by merging keys and values. Values for the same key are combined into a list.

    Parameters:
    - keys (list): List of keys.
    - values (list): List of values.

    Returns:
    - dict: Dictionary with merged values.
    """
    result = {}
    for key, value in zip(keys, values):
        if key in result:
            # Ensure the value is a list before appending
            if isinstance(result[key], list):
                result[key].append(value)
            else:
                result[key] = [result[key], value]
        else:
            result[key] = value  # Initialize as a list
    return result


def convert_code_to_name(list_codes):
    # Remove all digits from each item in the list
    list_codes_alpha = [re.sub(r'\d+', '', item) for item in list_codes]

    # Map the cleaned codes to names using the dictionary
    # If a code doesn't exist in the dictionary, keep the original code
    list_names = [dict_code_to_name[item] if item in dict_code_to_name else item for item in list_codes_alpha]

    return list_names

def check_directory_contains_csv(directory_path):
    """
    Check if a directory exists and contains at least one .csv file.

    Parameters:
    - directory_path (str): The path to the directory.

    Returns:
    - bool: True if the directory exists and contains at least one .csv file, False otherwise.
    """
    if os.path.isdir(directory_path):
        # Check for .csv files in the directory
        for file in os.listdir(directory_path):
            if file.endswith('.csv'):
                return True
    return False

def add_values_to_dict(existing_dict, key, values):
    """
    Add or append values to a dictionary key. If the key does not exist, it will be created.

    Parameters:
    - existing_dict (dict): The dictionary to update.
    - key: The key where values should be added.
    - values (list): A list of values to add.

    Returns:
    - None: Updates the dictionary in place.
    """
    if key not in existing_dict:
        # If key does not exist, create it with the new values as a list
        existing_dict[key] = values if isinstance(values, list) else [values]
    else:
        # If the key exists, extend the list of values
        if not isinstance(existing_dict[key], list):
            # Ensure the current value is a list
            existing_dict[key] = [existing_dict[key]]
        # Extend the list with the new values
        if isinstance(values, list):
            existing_dict[key].extend(values)
        else:
            existing_dict[key].append(values)


## --------------------------------------------------------------------------------------------------------------------
## Unique traits for the CEA-4 format
## --------------------------------------------------------------------------------------------------------------------


def cea4_verify_db(scenario, verbose=False):
    """
    Verify the database for the CEA-4 format.

    :param scenario: the scenario to verify
    :param verbose: if True, print the results
    :return: a dictionary with the missing files
    """

    dict_missing_db = {}

    #1. verify columns and values in .csv files for archetypes
    list_missing_files_csv_archetypes = verify_file_exists_4_db(scenario, ARCHETYPES)
    if list_missing_files_csv_archetypes:
        if verbose:
            print('! Ensure .csv file(s) are present in the ARCHETYPES folder: {list_missing_files_csv}.'.format(list_missing_files_csv=', '.join(map(str, list_missing_files_csv_archetypes))))
            # print('! CONSTRUCTION_TYPE.csv and USE_TYPE.csv are fundamental and should be present in the ARCHETYPES folder.')
            # print('! The CEA-4 Database verification is aborted.')
            # sys.exit(0)

    for item in ARCHETYPES:
        if item in list_missing_files_csv_archetypes:
            add_values_to_dict(dict_missing_db, item, item)
        else:
            list_missing_columns_csv_archetypes, list_issues_against_csv_archetypes = verify_file_against_schema_4_db(scenario, item)
            add_values_to_dict(dict_missing_db, item, list_missing_columns_csv_archetypes)
            add_values_to_dict(dict_missing_db, item, list_issues_against_csv_archetypes)
            if verbose:
                if list_missing_columns_csv_archetypes:
                    print('! Ensure column(s) are present in {item}.csv: {missing_columns}.'.format(item=item, missing_columns=', '.join(map(str, list_missing_columns_csv_archetypes))))
                if list_issues_against_csv_archetypes:
                    print('! Check value(s) in {item}.csv:')
                    print("\n".join(f"  {item}" for item in list_issues_against_csv_archetypes))

    #2. verify columns and values in .csv files for schedules
    if not dict_missing_db['USE_TYPE'] and check_directory_contains_csv(path_to_db_file_4(scenario, 'SCHEDULES')):
        use_type_df = pd.read_csv(path_to_db_file_4(scenario, 'USE_TYPE'))
        list_use_types = use_type_df['use_type'].tolist()
        list_missing_files_csv_schedules = verify_file_exists_4_db(scenario, SCHEDULES_FOLDER, sheet_name=list_use_types+['MONTHLY_MULTIPLIER'])
        if list_missing_files_csv_schedules:
            add_values_to_dict(dict_missing_db, 'SCHEDULES', list_missing_files_csv_schedules)
            if verbose:
                print('! Ensure .csv file(s) are present in the ARCHETYPES>SCHEDULES folder: {list_missing_files_csv}.'.format(list_missing_files_csv=', '.join(map(str, list_missing_files_csv_schedules))))
        if 'MONTHLY_MULTIPLIER' not in list_missing_files_csv_schedules:
            list_missing_monthly_multiplier_use_type = find_missing_values_column_column(path_to_db_file_4(scenario, 'USE_TYPE'), 'use_type', path_to_db_file_4(scenario, 'MONTHLY_MULTIPLIER'), 'use_type')
            list_missing_monthly_multiplier_schedules = find_missing_values_directory_column(path_to_db_file_4(scenario, 'SCHEDULES'), path_to_db_file_4(scenario, 'MONTHLY_MULTIPLIER'), 'use_type')
            list_missing_monthly_multiplier = list(set(list_missing_monthly_multiplier_use_type + list_missing_monthly_multiplier_schedules))
            if list_missing_monthly_multiplier:
                if verbose:
                    print('! Ensure use type(s) are defined in the MONTHLY_MULTIPLIER.csv: {list_missing_monthly_multiplier}.'.format(list_missing_monthly_multiplier=', '.join(map(str, list_missing_monthly_multiplier))))
                add_values_to_dict(dict_missing_db, 'SCHEDULES', list_missing_monthly_multiplier)
        for sheet in list_use_types:
            list_missing_columns_csv_schedules, list_issues_against_csv_schedules = verify_file_against_schema_4_db(scenario, 'SCHEDULES', sheet_name=sheet)
            add_values_to_dict(dict_missing_db, 'SCHEDULES', list_missing_columns_csv_schedules)
            if verbose:
                if list_missing_columns_csv_schedules:
                    print('! Ensure column(s) are present in {sheet}.csv: {missing_columns}.'.format(sheet=sheet, missing_columns=', '.join(map(str, list_missing_columns_csv_schedules))))
                if list_issues_against_csv_schedules:
                    print('! Check value(s) in {sheet}.csv:')
                    print("\n".join(f"  {item}" for item in list_issues_against_csv_schedules))
    elif 'use_type' in dict_missing_db['USE_TYPE']:
        add_values_to_dict(dict_missing_db, 'SCHEDULES', ['USE_TYPE'])
        if verbose:
            print('! Verification of .csv files for SCHEDULES was skipped because the use_type column is missing in USE_TYPE.csv.')
    else:
        add_values_to_dict(dict_missing_db, 'SCHEDULES', ['SCHEDULES'])

    #3. verify columns and values in .csv files for assemblies
    for ASSEMBLIES in ASSEMBLIES_FOLDERS:
        list_missing_files_csv_assemblies = verify_file_exists_4_db(scenario, [ASSEMBLIES], dict_ASSEMBLIES_COMPONENTS[ASSEMBLIES])
        add_values_to_dict(dict_missing_db, ASSEMBLIES, list_missing_files_csv_assemblies)
        if list_missing_files_csv_assemblies:
            if verbose:
                print('! Ensure .csv file(s) are present in the ASSEMBLIES>{ASSEMBLIES} folder: {list_missing_files_csv}.'.format(ASSEMBLIES=ASSEMBLIES, list_missing_files_csv=', '.join(map(str, list_missing_files_csv_assemblies))))

        list_list_missing_columns_csv = verify_assembly(scenario, ASSEMBLIES, list_missing_files_csv_assemblies, verbose)
        add_values_to_dict(dict_missing_db, ASSEMBLIES, [item for sublist in list_list_missing_columns_csv for item in sublist])

        list_existing_files_csv = list(set(dict_ASSEMBLIES_COMPONENTS[ASSEMBLIES]) - set(list_missing_files_csv_assemblies))
        # Verify is all values in the construction_type.csv file are defined in the assemblies.csv file
        dict_missing_assemblies = verify_assemblies_exist(scenario, ASSEMBLIES, list_existing_files_csv, dict_missing_db['CONSTRUCTION_TYPE'], archetypes='CONSTRUCTION_TYPE')
        list_missing_names_assemblies = list(dict_missing_assemblies.keys())
        add_values_to_dict(dict_missing_db, ASSEMBLIES, list_missing_names_assemblies)
        if list_missing_names_assemblies:
            if verbose:
                for key, values in dict_missing_assemblies.items():
                    print('! Ensure .csv file(s) are present in COMPONENTS>{ASSEMBLIES} folder: {missing_name_assemblies}, with assembly(ies) defined: {assemblies}.'.format(ASSEMBLIES=ASSEMBLIES, missing_name_assemblies=key, assemblies=', '.join(map(str, values))))

    #4. verify columns and values in .csv files for assemblies
    for COMPONENTS in COMPONENTS_FOLDERS:
        list_missing_files_csv_components = verify_file_exists_4_db(scenario, [COMPONENTS], dict_ASSEMBLIES_COMPONENTS[COMPONENTS])
        if list_missing_files_csv_components:
            if verbose:
                print('! Ensure .csv file(s) are present in the COMPONENTS>{COMPONENTS} folder: {list_missing_files_csv}.'.format(COMPONENTS=COMPONENTS, list_missing_files_csv=', '.join(map(str, list_missing_files_csv_components))))
            add_values_to_dict(dict_missing_db, COMPONENTS, list_missing_files_csv_components)
        else:
            add_values_to_dict(dict_missing_db, COMPONENTS, [])

    #5. verify columns and values in .csv files for components - conversion
    if not dict_missing_db['CONVERSION']:
        list_conversion_db = get_csv_filenames(path_to_db_file_4(scenario, 'CONVERSION'))
        dict_missing_conversion = verify_components_exist(scenario, 'SUPPLY', ['SUPPLY_HEATING', 'SUPPLY_COOLING'], ['primary_components', 'secondary_components', 'tertiary_components'], 'CONVERSION', code_to_name=True)
        if dict_missing_conversion:
            list_missing_names_conversion = list(dict_missing_conversion.keys())
            add_values_to_dict(dict_missing_db, 'CONVERSION', list_missing_names_conversion)
            if verbose:
                for key, values in dict_missing_conversion.items():
                    print('! Ensure .csv file(s) are present in COMPONENTS>CONVERSION folder: {missing_name_conversion}, with component(s) defined: {components}.'.format(missing_name_conversion=key, components=', '.join(map(str, values))))
        for sheet in list_conversion_db:
            list_missing_columns_csv_conversion, list_issues_against_csv_conversion = verify_file_against_schema_4_db(scenario, 'CONVERSION', sheet_name=sheet)
            add_values_to_dict(dict_missing_db, 'CONVERSION', list_missing_columns_csv_conversion)
            add_values_to_dict(dict_missing_db, 'CONVERSION', list_issues_against_csv_conversion)
            if verbose:
                if list_missing_columns_csv_conversion:
                    print('! Ensure column(s) are present in {conversion}.csv: {missing_columns}.'.format(conversion=sheet, missing_columns=', '.join(map(str, list_missing_columns_csv_conversion))))
                if list_issues_against_csv_conversion:
                    print('! Check value(s) in {conversion}.csv:')
                    print("\n".join(f"  {item}" for item in list_issues_against_csv_conversion))

    #6. verify columns and values in .csv files for components - distribution
    if not dict_missing_db['DISTRIBUTION']:
        list_missing_files_csv_distribution_components = verify_file_exists_4_db(scenario, ['DISTRIBUTION'], DISTRIBUTION_COMPONENTS)
        if list_missing_files_csv_distribution_components:
            print('! Ensure .csv file(s) are present in the COMPONENTS>DISTRIBUTION folder: {list_missing_files_csv}.'.format(list_missing_files_csv=', '.join(map(str, list_missing_files_csv_distribution_components))))

        for sheet in DISTRIBUTION_COMPONENTS:
            list_missing_columns_csv_distribution, list_issues_against_csv_distribution = verify_file_against_schema_4_db(scenario, 'DISTRIBUTION', sheet_name=sheet)
            add_values_to_dict(dict_missing_db, 'DISTRIBUTION', list_missing_columns_csv_distribution)
            add_values_to_dict(dict_missing_db, 'DISTRIBUTION', list_issues_against_csv_distribution)
            if verbose:
                if list_missing_columns_csv_distribution:
                    print('! Ensure column(s) are present in DISTRIBUTION.csv: {missing_columns}.'.format(missing_columns=', '.join(map(str, list_missing_columns_csv_distribution))))
                if list_issues_against_csv_distribution:
                    print('! Check value(s) in DISTRIBUTION.csv:')
                    print("\n".join(f"  {item}" for item in list_issues_against_csv_distribution))

    #7. verify columns and values in .csv files for components - feedstocks
    if not dict_missing_db['FEEDSTOCKS']:
        list_missing_files_csv_feedstocks_components = verify_file_exists_4_db(scenario, ['FEEDSTOCKS'], ['ENERGY_CARRIERS'])
        if list_missing_files_csv_feedstocks_components:
            print('! Ensure .csv file(s) are present in COMPONENTS>FEEDSTOCKS folder: {list_missing_files_csv}.'.format(list_missing_files_csv=', '.join(list_missing_files_csv_feedstocks_components)))
            add_values_to_dict(dict_missing_db, 'FEEDSTOCKS', list_missing_files_csv_feedstocks_components)

        list_feedstocks_db = get_csv_filenames(path_to_db_file_4(scenario, 'FEEDSTOCKS'))
        dict_missing_feedstocks = verify_components_exist(scenario, 'SUPPLY', SUPPLY_ASSEMBLIES, ['feedstock'], 'FEEDSTOCKS')
        if dict_missing_feedstocks:
            list_missing_names_feedstocks = list(dict_missing_feedstocks.keys())
            add_values_to_dict(dict_missing_db, 'FEEDSTOCKS', list_missing_names_feedstocks)
            if verbose:
                for key, _ in dict_missing_feedstocks.items():
                    print('! Ensure .csv file(s) are present in COMPONENTS>FEEDSTOCKS folder: {list_missing_feedstocks}.'.format(list_missing_feedstocks=', '.join(map(str, [key]))))
        if 'ENERGY_CARRIERS' not in list_missing_files_csv_feedstocks_components:
            list_missing_energy_carriers = find_missing_values_directory_column(path_to_db_file_4(scenario, 'FEEDSTOCKS'), path_to_db_file_4(scenario, 'FEEDSTOCKS', 'ENERGY_CARRIERS'), 'cost_and_ghg_tab')
            if list_missing_energy_carriers:
                if verbose:
                    print('! Ensure feedstock(s) are defined in the ENERGY_CARRIERS.csv: {list_missing_energy_carriers}.'.format(list_missing_energy_carriers=', '.join(map(str, list_missing_energy_carriers))))
                add_values_to_dict(dict_missing_db, 'FEEDSTOCKS', list_missing_energy_carriers)
        for sheet in list_feedstocks_db:
            list_missing_columns_csv_feedstocks, list_issues_against_csv_feedstocks = verify_file_against_schema_4_db(scenario, 'FEEDSTOCKS', sheet_name=sheet)
            add_values_to_dict(dict_missing_db, 'FEEDSTOCKS', list_missing_columns_csv_feedstocks)
            add_values_to_dict(dict_missing_db, 'FEEDSTOCKS', list_issues_against_csv_feedstocks)
            if verbose:
                if list_missing_columns_csv_feedstocks:
                    print('! Ensure column(s) are present in {feedstocks}.csv: {missing_columns}.'.format(feedstocks=sheet, missing_columns=', '.join(map(str, list_missing_columns_csv_feedstocks))))
                if list_issues_against_csv_feedstocks:
                    print('! Check value(s) in {feedstocks}.csv:')
                    print("\n".join(f"  {item}" for item in list_issues_against_csv_feedstocks))

    return dict_missing_db

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
    div_len = 37 - len(scenario_name)
    print('+' * 60)
    print("-" * 1 + ' Scenario: {scenario} '.format(scenario=scenario_name) + "-" * div_len)

    # Execute the verification
    dict_missing_db = cea4_verify_db(scenario, verbose=True)

    # Print the results
    print_verification_results_4_db(scenario_name, dict_missing_db)

    # Print the time used for the entire processing
    time_elapsed = time.perf_counter() - t0

    # Print: End
    print('+' * 60)
    print('The entire process of CEA-4 format verification is now completed - time elapsed: %.2f seconds' % time_elapsed)

if __name__ == '__main__':
    main(cea.config.Configuration())
