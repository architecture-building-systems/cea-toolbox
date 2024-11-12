"""
Batch processing CEA commands over all scenarios in a project.
This was originally explored and created for the ETH MiBS IDP 2023.
"""

# TODO: change the hard-coded path; this is subject to a structural separation of project-based CEA Features from scenario-based CEA Features

import os
import subprocess
import sys

import cea.config
import time

__author__ = "Zhongming Shi, Mathias Niffeler"
__copyright__ = "Copyright 2023, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Zhongming Shi, Mathias Niffeler"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"

# adding CEA to the environment
# Fix for running in PyCharm for users using micromamba
my_env = os.environ.copy()
my_env['PATH'] = f"{os.path.dirname(sys.executable)}:{my_env['PATH']}"

def exec_cea_commands(config, cea_scenario):
    """
    Automate user-defined CEA commands one after another.

    :param config: the configuration object to use
    :type config: cea.config.Configuration
    :param cea_scenario: path to the CEA scenario to be assessed using CEA
    :type cea_scenario: file path
    :return:
    """
    # acquire the user-defined CEA commands
    zone_csv_to_shp = config.batch_process_workflow.zone_csv_to_shp
    typology_csv_to_dbf = config.batch_process_workflow.typology_csv_to_dbf
    streets_csv_to_shp = config.batch_process_workflow.streets_csv_to_shp

    data_initializer = config.batch_process_workflow.data_initializer
    archetypes_mapper = config.batch_process_workflow.archetypes_mapper
    weather_helper = config.batch_process_workflow.weather_helper
    surroundings_helper = config.batch_process_workflow.surroundings_helper
    terrain_helper = config.batch_process_workflow.terrain_helper
    streets_helper = config.batch_process_workflow.streets_helper

    radiation = config.batch_process_workflow.radiation
    demand_forecasting = config.batch_process_workflow.demand_forecasting

    emissions = config.batch_process_workflow.emissions
    system_costs = config.batch_process_workflow.system_costs

    solar_pv = config.batch_process_workflow.solar_potential_pv
    solar_other = config.batch_process_workflow.solar_potential_other
    shallow_geothermal = config.batch_process_workflow.shallow_geothermal_potential
    water_body = config.batch_process_workflow.water_body_potential
    sewage_heat = config.batch_process_workflow.sewage_heat_potential

    thermal_network_layout = config.batch_process_workflow.thermal_network_layout
    thermal_network_operation = config.batch_process_workflow.thermal_network_operation

    optimization = config.batch_process_workflow.optimization

    # execute selected CEA commands
    if zone_csv_to_shp:
        zone_csv_path = os.path.join(cea_scenario, 'inputs/building-geometry/zone.csv')
        if not os.path.exists(zone_csv_path):
            zone_csv_path = os.path.join(cea_scenario, 'inputs/building-geometry/zone.xlsx')
        zone_out_path = os.path.join(cea_scenario, 'inputs/building-geometry')

        subprocess.run(['cea', 'shp-to-csv-to-shp',
                        '--scenario', cea_scenario,
                        '--input-file', zone_csv_path,
                        '--output-file-name', 'zone.shp',
                        '--output-path', zone_out_path,
                        # '--reference-shapefile', '{reference_shapefile_path}'.format(reference_shapefile_path=reference_shapefile_path),
                        '--polygon', 'true',
                        ], env=my_env, check=True, capture_output=True)

    if typology_csv_to_dbf:
        typology_csv_path = os.path.join(cea_scenario, 'inputs/building-properties/typology.csv')
        if not os.path.exists(typology_csv_path):
            typology_csv_path = os.path.join(cea_scenario, 'inputs/building-properties/typology.xlsx')
        typology_out_path = os.path.join(cea_scenario, 'inputs/building-properties')
        subprocess.run(['cea', 'dbf-to-csv-to-dbf', '--scenario', cea_scenario,
                        '--input-file', typology_csv_path,
                        '--output-file-name', 'typology.dbf',
                        '--output-path', typology_out_path,
                        ], env=my_env, check=True, capture_output=True)

    if data_initializer:
        subprocess.run(['cea', 'data-initializer', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
    if archetypes_mapper:
        subprocess.run(['cea', 'archetypes-mapper', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
    if weather_helper:
        subprocess.run(['cea', 'weather-helper', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
    if surroundings_helper:
        subprocess.run(['cea', 'surroundings-helper', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
    if terrain_helper:
        subprocess.run(['cea', 'terrain-helper', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
    if streets_helper:
        subprocess.run(['cea', 'streets-helper', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)

    if streets_csv_to_shp:
        streets_csv_path = os.path.join(cea_scenario, 'inputs/networks/streets.csv')
        if not os.path.exists(streets_csv_path):
            streets_csv_path = os.path.join(cea_scenario, 'inputs/networks/streets.xlsx')
        streets_out_path = os.path.join(cea_scenario, 'inputs/networks')
        reference_shapefile_path = os.path.join(cea_scenario, 'inputs/building-geometry/zone.shp')
        subprocess.run(['cea', 'shp-to-csv-to-shp', '--scenario', cea_scenario,
                        '--input-file', '{streets_csv_path}'.format(streets_csv_path=streets_csv_path),
                        '--output-file-name', 'streets.shp',
                        '--output-path', '{streets_out_path}'.format(streets_out_path=streets_out_path),
                        '--reference-shapefile',
                        '{reference_shapefile_path}'.format(reference_shapefile_path=reference_shapefile_path),
                        '--polygon', 'false',
                        ], env=my_env, check=True, capture_output=True)

    if radiation:
        subprocess.run(['cea', 'radiation', '--scenario', cea_scenario], env=my_env, check=True, capture_output=True)
    if demand_forecasting:
        subprocess.run(['cea', 'schedule-maker', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
        subprocess.run(['cea', 'demand', '--scenario', cea_scenario], env=my_env, check=True, capture_output=True)

    if emissions:
        subprocess.run(['cea', 'emissions', '--scenario', cea_scenario], env=my_env, check=True, capture_output=True)
    if system_costs:
        subprocess.run(['cea', 'system-costs', '--scenario', cea_scenario], env=my_env, check=True, capture_output=True)

    if solar_pv:
        subprocess.run(['cea', 'photovoltaic', '--scenario', cea_scenario], env=my_env, check=True, capture_output=True)
    if solar_other:
        subprocess.run(['cea', 'solar-collector', '--type-scpanel', 'FP', '--scenario', cea_scenario],
                       env=my_env, check=True, capture_output=True)
        subprocess.run(['cea', 'solar-collector', '--type-scpanel', 'ET', '--scenario', cea_scenario],
                       env=my_env, check=True, capture_output=True)
        subprocess.run(['cea', 'photovoltaic-thermal', '--type-scpanel', 'FP', '--scenario', cea_scenario],
                       env=my_env, check=True, capture_output=True)
        subprocess.run(['cea', 'photovoltaic-thermal', '--type-scpanel', 'ET', '--scenario', cea_scenario],
                       env=my_env, check=True, capture_output=True)
    if shallow_geothermal:
        subprocess.run(['cea', 'shallow-geothermal-potential', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
    if water_body:
        subprocess.run(['cea', 'water-body-potential', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
    if sewage_heat:
        subprocess.run(['cea', 'sewage-potential', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)

    if thermal_network_layout:
        subprocess.run(['cea', 'network-layout', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
    if thermal_network_operation:
        subprocess.run(['cea', 'thermal-network', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)

    if optimization:
        subprocess.run(['cea', 'decentralized', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)
        subprocess.run(['cea', 'optimization-new', '--scenario', cea_scenario], env=my_env, check=True,
                       capture_output=True)


def main(config):
    """
    Batch processing all scenarios under a project.

    :param config: the configuration object to use
    :type config: cea.config.Configuration
    :return:
    """

    # Start the timer
    t0 = time.perf_counter()

    assert os.path.exists(config.general.project), 'input file not found: %s' % config.project

    project_path = config.general.project
    scenario_name = config.general.scenario_name
    project_boolean = config.batch_process_workflow.all_scenarios

    # deciding to run all scenarios or the current the scenario only
    if project_boolean:
        scenarios_list = os.listdir(project_path)
    else:
        scenarios_list = [scenario_name]

    # loop over one or all scenarios under the project
    for scenario in scenarios_list:
        # Ignore hidden directories
        if scenario.startswith('.') or os.path.isfile(os.path.join(project_path, scenario)):
            continue

        cea_scenario = os.path.join(project_path, scenario)
        print(f'Executing CEA simulations on {cea_scenario}.')
        try:
            # executing CEA commands
            exec_cea_commands(config, cea_scenario)
        except subprocess.CalledProcessError as e:
            print(f"CEA simulation for scenario `{scenario_name}` failed at script: {e.cmd[1]}")
            print("Error Message:")
            err_msg = e.stderr
            if err_msg is not None:
                print(err_msg.decode())
            raise e

    # Read and summarise project results
    project_result_summary = config.batch_process_workflow.result_summary
    if project_result_summary and project_boolean:
        subprocess.run(['cea', 'result-summary', '--all-scenarios', 'true'], env=my_env, check=True, capture_output=True)
    elif project_result_summary and not project_boolean:
        subprocess.run(['cea', 'result-summary', '--all-scenarios', 'false'], env=my_env, check=True, capture_output=True)



    # Print the time used for the entire processing
    time_elapsed = time.perf_counter() - t0
    print('The entire batch processing sequence is now completed - time elapsed: %d.2 seconds' % time_elapsed)


if __name__ == '__main__':
    main(cea.config.Configuration())
