"""
Crossover routines

"""
from __future__ import division

from deap import tools


def crossover_main(ind1, ind2, indpb,
                   column_names,
                   heating_unit_names_share,
                   cooling_unit_names_share,
                   column_names_buildings_heating,
                   column_names_buildings_cooling,
                   district_heating_network,
                   district_cooling_network
                   ):
    # create dict of individual with his/her name
    ind1_with_name_dict = dict(zip(column_names, ind1))
    ind2_with_name_dict = dict(zip(column_names, ind2))

    if district_heating_network:

        # MUTATE BUILDINGS CONNECTED
        buildings_heating_ind1 = [ind1_with_name_dict[column] for column in column_names_buildings_heating]
        buildings_heating_ind2 = [ind2_with_name_dict[column] for column in column_names_buildings_heating]
        # apply crossover
        buildings_heating_ind1, buildings_heating_ind2 = tools.cxUniform(buildings_heating_ind1,
                                                                         buildings_heating_ind2,
                                                                         indpb)
        # take back to the individual
        for column, cross_over_value in zip(column_names_buildings_heating, buildings_heating_ind1):
            ind1_with_name_dict[column] = cross_over_value
        for column, cross_over_value in zip(column_names_buildings_heating, buildings_heating_ind2):
            ind2_with_name_dict[column] = cross_over_value

        # MUTATE SUPPLY SYSTEM UNITS SHARE
        heating_units_share_ind1 = [ind1_with_name_dict[column] for column in heating_unit_names_share]
        heating_units_share_ind2 = [ind2_with_name_dict[column] for column in heating_unit_names_share]
        # apply crossover
        heating_units_share_ind1, heating_units_share_ind2 = tools.cxUniform(heating_units_share_ind1,
                                                                             heating_units_share_ind2,
                                                                             indpb)
        # takeback to the individual
        for column, cross_over_value in zip(heating_unit_names_share, heating_units_share_ind1):
            ind1_with_name_dict[column] = cross_over_value
        for column, cross_over_value in zip(heating_unit_names_share, heating_units_share_ind2):
            ind2_with_name_dict[column] = cross_over_value

    if district_cooling_network:

        # CROSSOVER BUILDINGS CONNECTED
        buildings_cooling_ind1 = [ind1_with_name_dict[column] for column in column_names_buildings_cooling]
        buildings_cooling_ind2 = [ind2_with_name_dict[column] for column in column_names_buildings_cooling]
        # apply crossover
        buildings_cooling_ind1, buildings_cooling_ind2 = tools.cxUniform(buildings_cooling_ind1,
                                                                         buildings_cooling_ind2,
                                                                         indpb)
        # take back to teh individual
        for column, cross_over_value in zip(column_names_buildings_cooling, buildings_cooling_ind1):
            ind1_with_name_dict[column] = cross_over_value
        for column, cross_over_value in zip(column_names_buildings_cooling, buildings_cooling_ind2):
            ind2_with_name_dict[column] = cross_over_value

        # CROSSOVER SUPPLY SYSTEM UNITS SHARE
        cooling_units_share_ind1 = [ind1_with_name_dict[column] for column in cooling_unit_names_share]
        cooling_units_share_ind2 = [ind2_with_name_dict[column] for column in cooling_unit_names_share]
        # apply crossover
        cooling_units_share_ind1, cooling_units_share_ind2 = tools.cxUniform(cooling_units_share_ind1,
                                                                             cooling_units_share_ind2,
                                                                             indpb)
        # takeback to teh individual
        for column, cross_over_value in zip(cooling_unit_names_share, cooling_units_share_ind1):
            ind1_with_name_dict[column] = cross_over_value
        for column, cross_over_value in zip(cooling_unit_names_share, cooling_units_share_ind2):
            ind2_with_name_dict[column] = cross_over_value

    # now validate individual
    #THIS CROSSOVER (UNIFORM DOES NOT NEED VALIDATION BECAUSE NO DATA IS CHANGED.
    #IF THE CROSSOVER FUNCTION IS CHANGED WE MIGHT NEED SOME VALIDATION
    # from cea.optimization.master.validation import validation_main


    # now pass all the values mutated to the original individual
    for i, column in enumerate(column_names):
        ind1[i] = ind1_with_name_dict[column]

    for i, column in enumerate(column_names):
        ind2[i] = ind2_with_name_dict[column]

    return ind1, ind2
