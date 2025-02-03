"""
Main script of the formate helper that activates the verification and migration as needed.

"""

import os
import cea.config
import time

from cea.datamanagement.format_helper.cea4_migrate_db import migrate_cea3_to_cea4_db, path_to_db_file_3, delete_files
from cea.datamanagement.format_helper.cea4_verify import cea4_verify
from cea.datamanagement.format_helper.cea4_migrate import migrate_cea3_to_cea4

__author__ = "Zhongming Shi"
__copyright__ = "Copyright 2025, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Zhongming Shi"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"

from cea.datamanagement.format_helper.cea4_verify_db import cea4_verify_db

def exec_cea_format_helper(config, scenario):
    # auto-migrate from CEA-3 to CEA-4
    bool_migrate = config.format_helper.migrate_from_cea_3

    if not bool_migrate:
        dict_missing = cea4_verify(scenario, verbose=True)
        dict_missing_db = cea4_verify_db(scenario, verbose=True)

    else:
        migrate_cea3_to_cea4(scenario)
        dict_missing = cea4_verify(scenario, verbose=True)
        migrate_cea3_to_cea4_db(scenario)
        dict_missing_db = cea4_verify_db(scenario, verbose=True)

        if all(not value for value in dict_missing_db.values()):
            delete_files(path_to_db_file_3(scenario, 'technology'))

    return dict_missing, dict_missing_db


## --------------------------------------------------------------------------------------------------------------------
## Main function
## --------------------------------------------------------------------------------------------------------------------

def main(config):
    """
    Batch processing all selected scenarios under a project.

    :param config: the configuration object to use
    :type config: cea.config.Configuration
    :return:
    """

    # Start the timer
    t0 = time.perf_counter()

    assert os.path.exists(config.general.project), 'input file not found: %s' % config.general.project

    project_path = config.general.project
    scenarios_list = config.format_helper.scenarios_to_verify_and_migrate
    bool_migrate = config.format_helper.migrate_from_cea_3

    if bool_migrate:
        print('▼ Format Helper is batch-processing the data migration from CEA-3 to CEA-4 for Scenario(s): {scenarios_list}.'.format(scenarios_list=', '.join(scenarios_list)))
    else:
        print('▼ Format Helper is batch-processing the data verification for Scenario(s): {scenarios_list}.'.format(scenarios_list=', '.join(scenarios_list)))

    list_scenario_good = []
    list_scenario_problems = []
    log = []
    # Loop over one or all selected scenarios under the project
    for scenario in scenarios_list:
        # Ignore hidden directories
        if scenario.startswith('.') or os.path.isfile(os.path.join(project_path, scenario)):
            continue

        # Print: Start
        div_len = 91 - len(scenario)
        print('━' * 104)
        print("▼" * 1 + ' Scenario: {scenario} '.format(scenario=scenario) + "-" * div_len)

        cea_scenario = os.path.join(project_path, scenario)

        # executing CEA commands
        dict_missing, dict_missing_db = exec_cea_format_helper(config, cea_scenario)
        dict_result = {**dict_missing, **dict_missing_db}

        if all(not value for value in dict_result.values()):
            list_scenario_good.append(scenario)
        else:
            list_scenario_problems.append(scenario)
            log.append(dict_result)

    print('■' * 104)
    # Print the results
    if list_scenario_problems:
        print("!" * 3)
        print('Attentions on Scenario(s): {scenario}.'.format(scenario=', '.join(list_scenario_problems)))
        print('All or some of their Database\'s and/or input data\'s files/columns are missing or not fully compliant and compatible with CEA-4.')
        print('- If you are migrating your input data from CEA-3 to CEA-4 format, set the toggle `migrate_from_cea_3` to `True` for Feature CEA-4 Format Helper and click on Run. ')
        print('- If the toggle `migrate_from_cea_3` is already set to `True` or you manually prepared the Database and the input data, check the log for missing files and/or incompatible columns. Modify your Database and/or input data accordingly. Otherwise, all or some of the CEA simulations will fail.')

    if list_scenario_good:
        print("✓" * 3)
        print('All set for Scenario(s): {scenario}.'.format(scenario=', '.join(list_scenario_good)))
        print('Their Database and input data are (now) fully compliant and compatible with CEA-4.')

    # Print the time used for the entire processing
    time_elapsed = time.perf_counter() - t0
    print('■' * 104)
    if bool_migrate:
        print('CEA\'s attempt to migrate the Database and the input data for CEA-4 is now completed - time elapsed: %.2f seconds.' % time_elapsed)
    else:
        print('CEA\'s attempt to verify the Database and the input data for CEA-4 is now completed - time elapsed: %.2f seconds.' % time_elapsed)


if __name__ == '__main__':
    main(cea.config.Configuration())
