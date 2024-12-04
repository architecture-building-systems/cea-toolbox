import json
import os
import pathlib
import shutil
import traceback
from typing import Dict, Any

import geopandas
import pandas as pd
from fastapi import APIRouter, HTTPException, status
from fiona.errors import DriverError
from pydantic import BaseModel
from fastapi.concurrency import run_in_threadpool

import cea.inputlocator
import cea.schemas
import cea.scripts
import cea.utilities.dbf
from cea.datamanagement.databases_verification import InputFileValidator
from cea.interfaces.dashboard.api.databases import read_all_databases, DATABASES_SCHEMA_KEYS
from cea.interfaces.dashboard.dependencies import CEAConfig
from cea.interfaces.dashboard.utils import secure_path
from cea.plots.supply_system.a_supply_system_map import get_building_connectivity, newer_network_layout_exists
from cea.plots.variable_naming import get_color_array
from cea.technologies.network_layout.main import layout_network, NetworkLayout
from cea.utilities.schedule_reader import schedule_to_file, get_all_schedule_names, schedule_to_dataframe, \
    read_cea_schedule, save_cea_schedule
from cea.utilities.standardize_coordinates import get_geographic_coordinate_system

router = APIRouter()

COLORS = {
    'surroundings': get_color_array('grey_light'),
    'dh': get_color_array('red'),
    'dc': get_color_array('blue'),
    'disconnected': get_color_array('white')
}

# List of input databases (db_name, locator/schema_key)
INPUT_DATABASES = [
    ('zone', 'get_zone_geometry'),
    ('typology', 'get_building_typology'),
    ('architecture', 'get_building_architecture'),
    ('internal-loads', 'get_building_internal'),
    ('indoor-comfort', 'get_building_comfort'),
    ('air-conditioning-systems', 'get_building_air_conditioning'),
    ('supply-systems', 'get_building_supply'),
    ('surroundings', 'get_surroundings_geometry'),
    ('trees', "get_tree_geometry")
]


def get_input_database_schemas():
    """Parse the schemas.yml file and create the dictionary of column types"""
    schemas = cea.schemas.schemas(plugins=[])
    input_database_schemas = dict()
    for db_name, locator in INPUT_DATABASES:
        schema = schemas[locator]
        input_database_schemas[db_name] = {
            'file_type': schema['file_type'],
            'location': locator,
            'columns': schema['schema']['columns']
        }
    return input_database_schemas


INPUTS = get_input_database_schemas()
INPUT_KEYS = INPUTS.keys()
GEOJSON_KEYS = ['zone', 'surroundings', 'trees', 'streets', 'dc', 'dh']
NETWORK_KEYS = ['dc', 'dh']


@router.get("/")
async def get_keys():
    return {'buildingProperties': INPUT_KEYS, 'geoJSONs': GEOJSON_KEYS}


@router.get('/building-properties/{db}')
async def get_building_props_db(db: str):
    if db not in INPUTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Input file not found: {db}',
        )
    db_info = INPUTS[db]
    columns = dict()
    for column_name, column in db_info['columns'].items():
        columns[column_name] = column['type']
    return columns


@router.get('/geojson/{kind}')
async def get_input_geojson(config: CEAConfig, kind: str):
    locator = cea.inputlocator.InputLocator(config.scenario)

    if kind not in GEOJSON_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Input file not found: {kind}',
        )
    # Building geojsons
    elif kind in INPUT_KEYS and kind in GEOJSON_KEYS:
        db_info = INPUTS[kind]
        locator = cea.inputlocator.InputLocator(config.scenario)
        location = getattr(locator, db_info['location'])()
        if db_info['file_type'] != 'shp':
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Invalid database for geojson: {location}',
            )
        return df_to_json(location)[0]
    elif kind in NETWORK_KEYS:
        return get_network(config, kind)[0]
    elif kind == 'streets':
        return df_to_json(locator.get_street_network())[0]


@router.get('/building-properties')
async def get_building_props(config: CEAConfig):
    return get_building_properties(config)


@router.get('/all-inputs')
async def get_all_inputs(config: CEAConfig):
    locator = cea.inputlocator.InputLocator(config.scenario)

    # FIXME: Find a better way, current used to test for Input Editor
    def fn():
        store = get_building_properties(config)
        store['geojsons'] = {}
        store['connected_buildings'] = {'dc': [], 'dh': []}
        store['crs'] = {}
        store['geojsons']['zone'], store['crs']['zone'] = df_to_json(locator.get_zone_geometry())
        store['geojsons']['surroundings'], store['crs']['surroundings'] = df_to_json(
            locator.get_surroundings_geometry())
        store['geojsons']['trees'], store['crs']['trees'] = df_to_json(locator.get_tree_geometry())
        store['geojsons']['streets'], store['crs']['streets'] = df_to_json(locator.get_street_network())
        # store['geojsons']['dc'], store['connected_buildings']['dc'], store['crs']['dc'] = get_network(config, 'dc')
        # store['geojsons']['dh'], store['connected_buildings']['dh'],  store['crs']['dh'] = get_network(config, 'dh')
        store['geojsons']['dc'] = None
        store['geojsons']['dh'] = None
        store['colors'] = COLORS
        store['schedules'] = {}

        return store

    return await run_in_threadpool(fn)


class InputForm(BaseModel):
    tables: Dict[str, Any] = {}
    geojsons: Dict[str, Any] = {}
    crs: Dict[str, Any] = {}
    schedules: Dict[str, Any] = {}


@router.put('/all-inputs')
async def save_all_inputs(config: CEAConfig, form: InputForm):
    locator = cea.inputlocator.InputLocator(config.scenario)

    tables = form.tables
    geojsons = form.geojsons
    crs = form.crs
    schedules = form.schedules

    def fn():
        out = {'tables': {}, 'geojsons': {}}

        # TODO: Maybe save the files to temp location in case something fails
        for db in INPUTS:
            db_info = INPUTS[db]
            location = getattr(locator, db_info['location'])()
            file_type = db_info['file_type']

            if tables.get(db) is None:  # ignore if table does not exist
                continue

            if len(tables[db]):
                if file_type == 'shp':
                    table_df = geopandas.GeoDataFrame.from_features(geojsons[db]['features'],
                                                                    crs=get_geographic_coordinate_system())
                    out['geojsons'][db] = json.loads(table_df.to_json())
                    table_df = table_df.to_crs(crs[db])
                    table_df.to_file(location, driver='ESRI Shapefile', encoding='ISO-8859-1')

                    table_df = pd.DataFrame(table_df.drop(columns='geometry'))
                    out['tables'][db] = json.loads(table_df.set_index('Name').to_json(orient='index'))
                elif file_type == 'dbf':
                    table_df = pd.read_json(json.dumps(tables[db]), orient='index')

                    # Make sure index name is 'Name;
                    table_df.index.name = 'Name'
                    table_df = table_df.reset_index()

                    cea.utilities.dbf.dataframe_to_dbf(table_df, location)
                    out['tables'][db] = json.loads(table_df.set_index('Name').to_json(orient='index'))

            else:  # delete file if empty unless it is surroundings (allow for empty surroundings file)
                if db == "surroundings":
                    table_df = geopandas.GeoDataFrame(columns=["Name", "height_ag", "floors_ag"], geometry=[],
                                                      crs=get_geographic_coordinate_system())
                    table_df.to_file(location)

                    out['tables'][db] = []

                elif os.path.isfile(location):
                    if file_type == 'shp':
                        import glob
                        for filepath in glob.glob(os.path.join(locator.get_building_geometry_folder(), '%s.*' % db)):
                            os.remove(filepath)
                    elif file_type == 'dbf':
                        os.remove(location)

                if file_type == 'shp':
                    out['geojsons'][db] = {}

        if schedules:
            for building in schedules:
                schedule_dict = schedules[building]
                schedule_path = locator.get_building_weekly_schedules(building)
                schedule_data = schedule_dict['SCHEDULES']
                schedule_complementary_data = {'MONTHLY_MULTIPLIER': schedule_dict['MONTHLY_MULTIPLIER'],
                                               'METADATA': schedule_dict['METADATA']}
                data = pd.DataFrame()
                for day in ['WEEKDAY', 'SATURDAY', 'SUNDAY']:
                    df = pd.DataFrame({'HOUR': range(1, 25), 'DAY': [day] * 24})
                    for schedule_type, schedule in schedule_data.items():
                        df[schedule_type] = schedule[day]
                    data = pd.concat([df, data], ignore_index=True)
                save_cea_schedule(data.to_dict('list'), schedule_complementary_data, schedule_path)
                print('Schedule file written to {}'.format(schedule_path))

        return out

    return await run_in_threadpool(fn)


def get_building_properties(config):
    locator = cea.inputlocator.InputLocator(config.scenario)
    store = {'tables': {}, 'columns': {}}
    for db in INPUTS:
        db_info = INPUTS[db]
        locator_method = db_info['location']
        file_path = getattr(locator, locator_method)()
        file_type = db_info['file_type']
        db_columns = db_info['columns']

        if file_path is None:
            print(locator_method, file_path)

        try:
            if file_type == 'shp':
                table_df = geopandas.read_file(file_path)
                table_df = pd.DataFrame(
                    table_df.drop(columns='geometry'))
                if 'geometry' in db_columns:
                    del db_columns['geometry']
                if 'REFERENCE' in db_columns and 'REFERENCE' not in table_df.columns:
                    table_df['REFERENCE'] = None
                store['tables'][db] = json.loads(
                    table_df.set_index('Name').to_json(orient='index'))
            else:
                assert file_type == 'dbf', 'Unexpected database type: %s' % file_type
                table_df = cea.utilities.dbf.dbf_to_dataframe(file_path)
                if 'REFERENCE' in db_columns and 'REFERENCE' not in table_df.columns:
                    table_df['REFERENCE'] = None
                store['tables'][db] = json.loads(
                    table_df.set_index('Name').to_json(orient='index'))

            columns = {}
            for column_name, column in db_columns.items():
                columns[column_name] = {}
                if column_name == 'REFERENCE':
                    continue
                columns[column_name]['type'] = column['type']
                if 'choice' in column:
                    path = getattr(locator, column['choice']['lookup']['path'])()
                    columns[column_name]['path'] = path
                    # TODO: Try to optimize this step to decrease the number of file reading
                    columns[column_name]['choices'] = get_choices(column['choice'], path)
                if 'constraints' in column:
                    columns[column_name]['constraints'] = column['constraints']
                if 'regex' in column:
                    columns[column_name]['regex'] = column['regex']
                    if 'example' in column:
                        columns[column_name]['example'] = column['example']
                if 'nullable' in column:
                    columns[column_name]['nullable'] = column['nullable']
                columns[column_name]['description'] = column["description"]
                columns[column_name]['unit'] = column["unit"]
            store['columns'][db] = columns

        except (IOError, DriverError, ValueError) as e:
            print(e)
            store['tables'][db] = None
            store['columns'][db] = None

    return store


def get_network(config, network_type):
    # TODO: Get a list of names and send all in the json
    try:
        locator = cea.inputlocator.InputLocator(config.scenario)
        building_connectivity = get_building_connectivity(locator)
        network_type = network_type.upper()
        connected_buildings = building_connectivity[building_connectivity['{}_connectivity'.format(
            network_type)] == 1]['Name'].values.tolist()
        network_name = 'today'

        # Do not calculate if no connected buildings
        if len(connected_buildings) < 2:
            return None, [], None

        # Generate network files
        if newer_network_layout_exists(locator, network_type, network_name):
            config.network_layout.network_type = network_type
            config.network_layout.connected_buildings = connected_buildings
            # Ignore demand and creating plants for layout in map
            config.network_layout.consider_only_buildings_with_demand = False
            network_layout = NetworkLayout(network_layout=config.network_layout)
            layout_network(network_layout, locator, output_name_network=network_name)

        edges = locator.get_network_layout_edges_shapefile(network_type, network_name)
        nodes = locator.get_network_layout_nodes_shapefile(network_type, network_name)

        network_json, crs = df_to_json(edges)
        if network_json is None:
            return None, [], None

        nodes_json, _ = df_to_json(nodes)
        network_json['features'].extend(nodes_json['features'])
        network_json['properties'] = {'connected_buildings': connected_buildings}
        return network_json, connected_buildings, crs
    except IOError as e:
        print(e)
        return None, [], None
    except Exception:
        traceback.print_exc()
        return None, [], None


def df_to_json(file_location):
    from cea.utilities.standardize_coordinates import get_lat_lon_projected_shapefile, get_projected_coordinate_system

    try:
        table_df = geopandas.GeoDataFrame.from_file(file_location)
        # Save coordinate system
        if table_df.empty:
            # Set crs to generic projection if empty
            crs = table_df.crs.to_proj4()
        else:
            lat, lon = get_lat_lon_projected_shapefile(table_df)
            crs = get_projected_coordinate_system(lat, lon)

        if "Name" in table_df.columns:
            table_df['Name'] = table_df['Name'].astype('str')

        # make sure that the geojson is coded in latitude / longitude
        out = table_df.to_crs(get_geographic_coordinate_system())
        out = json.loads(out.to_json())
        return out, crs
    except (IOError, DriverError) as e:
        print(e)
        return None, None
    except Exception:
        traceback.print_exc()
        return None, None


@router.get('/building-schedule/{building}')
async def get_building_schedule(config: CEAConfig, building: str):
    locator = cea.inputlocator.InputLocator(config.scenario)
    try:
        schedule_path = secure_path(locator.get_building_weekly_schedules(building))
        schedule_data, schedule_complementary_data = read_cea_schedule(schedule_path)
        df = pd.DataFrame(schedule_data).set_index(['DAY', 'HOUR'])
        out = {'SCHEDULES': {
            schedule_type: {day: df.loc[day][schedule_type].values.tolist() for day in df.index.levels[0]}
            for schedule_type in df.columns}}
        out.update(schedule_complementary_data)
        return out
    except IOError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get('/databases')
async def get_input_database_data(config: CEAConfig):
    locator = cea.inputlocator.InputLocator(config.scenario)
    try:
        return await run_in_threadpool(lambda: read_all_databases(locator.get_databases_folder()))
    except IOError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put('/databases')
async def put_input_database_data(config: CEAConfig, payload: Dict[str, Any]):
    locator = cea.inputlocator.InputLocator(config.scenario)

    for db_type in payload:
        for db_name in payload[db_type]:
            if db_name == 'USE_TYPES':
                database_dict_to_file(payload[db_type]['USE_TYPES']['USE_TYPE_PROPERTIES'],
                                      locator.get_database_use_types_properties())
                for archetype, schedule_dict in payload[db_type]['USE_TYPES']['SCHEDULES'].items():
                    schedule_dict_to_file(
                        schedule_dict,
                        locator.get_database_standard_schedules_use(
                            archetype
                        )
                    )
            else:
                locator_method = DATABASES_SCHEMA_KEYS[db_name][0]
                db_path = locator.__getattribute__(locator_method)()
                database_dict_to_file(payload[db_type][db_name], db_path)

    return payload


class DatabasePath(BaseModel):
    path: pathlib.Path
    name: str


@router.put('/databases/copy')
async def copy_input_database(config: CEAConfig, database_path: DatabasePath):
    locator = cea.inputlocator.InputLocator(config.scenario)

    copy_path = secure_path(os.path.join(database_path.path, database_path.name))
    if os.path.exists(copy_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Copy path {copy_path} already exists. Choose a different path/name.',
        )
    locator.ensure_parent_folder_exists(copy_path)
    shutil.copytree(locator.get_databases_folder(), copy_path)
    return {'message': 'Database copied to {}'.format(copy_path)}


@router.get('/databases/check')
async def check_input_database(config: CEAConfig):
    locator = cea.inputlocator.InputLocator(config.scenario)
    try:
        locator.verify_database_template()
    except IOError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    return {'message': 'Database in path seems to be valid.'}


@router.get("/databases/validate")
async def validate_input_database(config: CEAConfig):
    import cea.scripts
    locator = cea.inputlocator.InputLocator(config.scenario)
    schemas = cea.schemas.schemas(plugins=[])
    validator = InputFileValidator(locator, plugins=config.plugins)
    out = dict()

    for db_name, schema_keys in DATABASES_SCHEMA_KEYS.items():
        for schema_key in schema_keys:
            schema = schemas[schema_key]
            if schema_key != 'get_database_standard_schedules_use':
                db_path = locator.__getattribute__(schema_key)()
                try:
                    df = pd.read_excel(db_path, sheet_name=None)
                    errors = validator.validate(df, schema)
                    if errors:
                        out[db_name] = errors
                except IOError:
                    out[db_name] = [{}, 'Could not find or read file: {}'.format(db_path)]
            else:
                for use_type in get_all_schedule_names(locator.get_database_use_types_folder()):
                    db_path = locator.__getattribute__(schema_key)(use_type)
                    try:
                        df = schedule_to_dataframe(db_path)
                        errors = validator.validate(df, schema)
                        if errors:
                            out[use_type] = errors
                    except IOError:
                        out[use_type] = [{}, 'Could not find or read file: {}'.format(db_path)]
    return out


def database_dict_to_file(db_dict, db_path):
    with pd.ExcelWriter(db_path) as writer:
        for sheet_name, data in db_dict.items():
            df = pd.DataFrame(data).dropna(axis=0, how='all')
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    print('Database file written to {}'.format(db_path))


def schedule_dict_to_file(schedule_dict, schedule_path):
    schedule = dict()
    for key, data in schedule_dict.items():
        schedule[key] = pd.DataFrame(data)
    schedule_to_file(schedule, schedule_path)


def get_choices(choice_properties, path):
    lookup = choice_properties['lookup']
    df = pd.read_excel(path, lookup['sheet'])
    choices = df[lookup['column']].tolist()
    out = []
    if 'none_value' in choice_properties:
        out.append({'value': choice_properties['none_value'], 'label': ''})
    for choice in choices:
        label = df.loc[df[lookup['column']] == choice, 'Description'].values[0] if 'Description' in df.columns else ''

        # Prevent labels to be encoded as NaN in JSON
        if str(label) == 'nan':
            label = 'none'
        out.append({'value': choice, 'label': label})
    return out
