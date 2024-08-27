"""
Print the set of non-dominated solutions identified by the optimization algorithm. This plot integrates an option
to chose the objective function space in which the solutions are plotted. The user must chose exactly 2  of the
objective functions used to run the optimization.
"""

__author__ = "Mathias Niffeler"
__copyright__ = "Copyright 2023, Cooling Singapore"
__credits__ = ["Mathias Niffeler"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "NA"
__email__ = "mathias.niffeler@sec.ethz.ch"
__status__ = "Production"


import csv
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.optimize import curve_fit

import cea.config
from cea.inputlocator import InputLocator


def read_objective_values(file_path):
    """
    Read the objective function and the solution's objective function values from the optimization results file.
    """
    with open(file_path, 'r') as file:
        # Read the file
        reader = csv.reader(file)
        headers = next(reader)  # Read header row
        objectives = headers[1:] # Get the objective function names

        # Read the objective function values
        for row in reader:
            if row[0] == 'Total':
                values = [float(value) for value in row[1:]]

        return objectives, values

def read_network_costs(file_path):
    """
    Read the network costs from the detailed optimization results file.
    """
    if not os.path.isfile(file_path):
        return 0

    with open(file_path, 'r') as file:
        # Read the file
        reader = csv.reader(file)
        network_data_headers = next(reader)  # Read header row
        cost_column = network_data_headers.index('Network cost [USD]')  # Read network

        # Read network costs
        total_network_cost_usd = 0
        for row in reader:
            total_network_cost_usd += float(row[cost_column])

        return total_network_cost_usd

def read_objective_values_from_file(file_paths):
    """
    Extract the selected objective functions and the non-dominated solutions' objective function values from the
    optimization results files.
    """
    # Initialize objects to store the objectives and the solutions' objective function values
    objectives = []
    objective_function_values_df = pd.DataFrame()

    # Read the objective function values from the optimization results file
    for file_path in file_paths:
        new_objectives, values = read_objective_values(file_path)

        # Check if the objective functions are the same for all the optimization results
        if not objectives:
            objectives = new_objectives
        else:
            assert objectives == new_objectives, 'There is a mismatch in the objective functions used for the '\
                                                 'optimization. Please check the optimization results.'

        # Get the DCS-solution code from the file path and use it as a key to store the objective function values
        objective_function_values_df = \
            pd.concat([objective_function_values_df, pd.DataFrame([file_path.split(os.sep)[-3]] + values).T],
                      axis=0, sort=False,  ignore_index=False)

    # Rename the columns of the dataframe and reset the indexes
    objective_function_values_df.reset_index(inplace=True, drop=True)
    objective_function_values_df.columns = ['DCS-solution'] + objectives

    return objectives, objective_function_values_df

def read_network_costs_from_file(file_paths):
    """
    Extract the network costs from the results files for each non-dominated solution.
    """
    # Read the supply system code and the network costs from the optimization results files
    network_lifetime = 20 # Todo: properly implement the network lifetime
    system_id = [file_path.split(os.sep)[-3] for file_path in file_paths]
    network_costs = [read_network_costs(file_path)/network_lifetime for file_path in file_paths]

    # Create a dataframe with the supply system code and the network costs
    network_costs_df = pd.DataFrame({'DCS-solution': system_id, 'Network cost [USD]': network_costs})

    return network_costs_df

def find_control_point(x, y):
    """Calculate the point used as the control point in the Bézier curve."""
    nbr_points = len(x)
    quarter= int(nbr_points / 4)

    x_control = x[quarter]
    y_control = y[-quarter]
    return x_control, y_control


def fit_bezier_curve_with_mean_control_point(x, y):
    """Fit a quadratic Bézier curve using the mean point as the control point and return the curve with shading coordinates."""
    p_control = find_control_point(x, y)

    t = np.linspace(0, 1, 300)
    curve_x = bezier_curve(t, x[0], p_control[0], x[-1])
    curve_y = bezier_curve(t, y[0], p_control[1], y[-1])

    # Extend the curve to create a shaded area (to the right and above the entire plot)
    x_extension = max(curve_x) + (max(curve_x) - min(curve_x)) * 0.5
    y_extension = max(curve_y) + (max(curve_y) - min(curve_y)) * 0.5

    shade_x = np.concatenate([curve_x, [x_extension], [x_extension], [curve_x[0]]])
    shade_y = np.concatenate([curve_y, [curve_y[-1]], [y_extension], [y_extension]])

    return curve_x, curve_y, shade_x, shade_y


def bezier_curve(t, P0, P1, P2):
    """Quadratic Bézier curve function."""
    return (1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t ** 2 * P2


def plot_pareto_front(objectives, objective_values_dict):
    """
    Create a series of scatter plots to visualize the Pareto fronts of the optimization for multiple runs.
    Draw Bézier curves through the points belonging to each non-dominated front using the mean point as the control point,
    and shade the area above and to the right of the curve to cover the top-right quadrant.
    """
    nbr_traces = len(objectives) * (len(objectives) - 1) * len(objective_values_dict) * 2
    base_visibility = [False] * nbr_traces
    traces = []
    buttons = []
    colors = ['blue', 'green', 'red', 'purple', 'orange', 'yellow']

    for i in range(len(objectives)):
        for j in range(i + 1, len(objectives)):
            current_traces = []
            for run_id, objective_values in objective_values_dict.items():
                color = colors[run_id % len(colors)]

                # Scatter plot for the current run (including 'current_DES')
                current_traces.append(go.Scatter(
                    x=objective_values[objectives[i]],
                    y=objective_values[objectives[j]],
                    mode='markers',
                    name=f'DCS-solution run {run_id}',
                    text=objective_values['DCS-solution'],
                    marker=dict(
                        size=12,
                        color=color,
                        line=dict(width=2, color='black'),
                        opacity=0.8
                    ),
                    visible=False
                ))

                # Exclude 'current_DES' from the fitting process
                fit_data = objective_values[objective_values['DCS-solution'] != 'current_DES']

                # Fit Bézier curve to the Pareto front using the mean control point and get the shading coordinates
                try:
                    curve_x, curve_y, shade_x, shade_y = fit_bezier_curve_with_mean_control_point(
                        np.array(fit_data[objectives[i]], dtype=float),
                        np.array(fit_data[objectives[j]], dtype=float))

                    # Add the fitted Bézier curve to the plot
                    current_traces.append(go.Scatter(
                        x=curve_x,
                        y=curve_y,
                        mode='lines',
                        line=dict(color=color, width=2),
                        name=f'Fitted Bézier run {run_id}',
                        visible=False
                    ))

                    # Add the shaded area above and to the right of the curve
                    current_traces.append(go.Scatter(
                        x=shade_x,
                        y=shade_y,
                        fill='toself',
                        fillcolor=color,
                        line=dict(color='rgba(255,255,255,0)'),  # No border line
                        name=f'Suggested solution space {run_id}',
                        visible=False,
                        opacity=0.3  # Adjust opacity for shading
                    ))

                except Exception as e:
                    print(
                        f"Bézier fitting failed for run {run_id} with objectives {objectives[i]} and {objectives[j]}: {e}")

            visibility = base_visibility.copy()
            visibility[len(traces):len(traces) + len(current_traces)] = [True] * len(current_traces)
            buttons.append(dict(
                args=[{'visible': visibility},
                      {'xaxis.title.text': objectives[i],
                       'yaxis.title.text': objectives[j]}],
                label=f'{objectives[i]} vs {objectives[j]}',
                method='update'
            ))
            traces.extend(current_traces)

    for trace in traces[:len(objective_values_dict) * 2]:
        trace.visible = True

    layout = go.Layout(
        title='Pareto Front Comparison',
        xaxis=dict(title=objectives[0]),
        yaxis=dict(title=objectives[1]),
        width=800,
        height=600,
        showlegend=True,
        plot_bgcolor='rgb(190, 235, 243)',
        updatemenus=[dict(
            buttons=buttons,
            direction='down',
            pad={'r': 10, 't': 10},
            showactive=True,
            x=0.1,
            xanchor='left',
            y=1.13,
            yanchor='top'
        )]
    )

    fig = go.Figure(data=traces, layout=layout)
    fig.update_xaxes(ticks='outside', gridcolor='grey')
    fig.update_yaxes(ticks='outside', gridcolor='grey')
    fig.show()

def add_3D_scatter_plot(objectives, objective_values):
        # Create 3D scatter plots if there are 3 or more objective functions, introduce corresponding elements to the
    #   drop-down menu and add them to the list of traces

    if len(objectives) >= 3:
        data = go.Scatter3d(x=objective_values[objectives[0]],
                            y=objective_values[objectives[1]],
                            z=objective_values[objectives[3]],
                            mode='markers',
                            name='DCS-solution',
                            text=objective_values['DCS-solution'],
                            marker=dict(
                                size=15,
                                color=[int(code.split('_')[-1]) for code in objective_values['DCS-solution']
                                       if code.split('_')[-1].isdigit()],
                                colorscale='Viridis',
                                opacity=0.9,
                                line=dict(width=4,
                                          color='black')
                            )
                            )


        # Customize the layout
        layout = go.Layout(scene=dict(xaxis_title=objectives[0],
                                      yaxis_title=objectives[1],
                                      zaxis_title=objectives[3],
                                      xaxis=dict(
                                          ticks='outside',
                                          backgroundcolor="rgb(254, 253, 224)",
                                          gridcolor="grey",
                                          showbackground=True),
                                      yaxis=dict(
                                          ticks='outside',
                                          backgroundcolor="rgb(255, 238, 217)",
                                          gridcolor="grey",
                                          showbackground=True),
                                      zaxis=dict(
                                          ticks='outside',
                                          backgroundcolor="rgb(190, 235, 243)",
                                          gridcolor="grey",
                                          showbackground=True)
                                      )
                           )

        # Show the plot
        fig = go.Figure(data=data, layout=layout)
        fig.show()


def main(config=cea.config.Configuration()):
    """Test this plot"""
    run_ids = [1, 4]  # List of run IDs to compare
    locator = InputLocator(scenario=config.scenario)
    objective_values_dict = {}

    for run_id in run_ids:
        optimisation_results = locator.get_new_optimization_results_folder(run_id=run_id)
        individual_supply_system_results = [
            locator.get_new_optimization_optimal_supply_systems_summary_file(run_id, subfolder)
            for subfolder in os.listdir(optimisation_results) if not subfolder == 'debugging'
        ]
        objectives, objective_function_values = read_objective_values_from_file(individual_supply_system_results)

        if 'Cost_USD' in objectives:
            individual_network_results = [
                locator.get_new_optimization_detailed_network_performance_file(subfolder)
                for subfolder in os.listdir(optimisation_results) if not subfolder == 'debugging'
            ]
            network_costs = read_network_costs_from_file(individual_network_results)
            total_system_cost = network_costs['Network cost [USD]'] + objective_function_values['Cost_USD']
            objective_function_values['Cost_USD'] = total_system_cost

        objective_values_dict[run_id] = objective_function_values

    plot_pareto_front(objectives, objective_values_dict)

if __name__ == '__main__':
    main(cea.config.Configuration())