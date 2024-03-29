"""Graphical visualization of the profiles made by `web` collector"""

import os
import webbrowser

import click
import shlex
import subprocess
import pandas as pd
import seaborn as sns
import holoviews as hv
import perun.profile.factory as profile_factory

from holoviews import opts
from typing import Any, List, Union
from matplotlib import pyplot as plt
from perun.view.web.unsupported_metric_exception import UnsupportedMetricException


output_dir = "view/"


def generate_psutil(data: List[dict[str, Any]], metric: str, show: bool,) -> None:
    """https://holoviews.org/gallery/apps/bokeh/streaming_psutil.html"""


def generate_heatmap(data: List[dict[str, Any]], metric: str, show: bool, group_by: str = "20s") -> None:
    """Heatmap for supported metrics of web collector
    You need to define labels for new metric in `get_graph_labels`, if it is not done already.
    https://holoviews.org/reference/elements/plotly/HeatMap.html

    Args:
        data (List[Dict[str, Any]]): The data to be plotted.
        metric (str): The metric to be visualized.
        show (bool): Whether to display the heatmap.
        group_by (str, optional): The time interval for grouping the data. Defaults to "20s".

    Returns:
        None
    """

    hv.extension("bokeh")

    df = pd.DataFrame(data)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["time_group"] = df["timestamp"].dt.floor(group_by)
    df["time"] = df["time_group"].dt.strftime("%H:%M:%S")
    df["amount"] = pd.to_numeric(df["amount"])
    df['count'] = 1

    df_filtered = df[df["type"] == metric]
    df_agg = df_filtered.groupby(['time', 'amount']).count().reset_index()

    max_count = df_agg['count'].max()
    df_agg['normalized_count'] = df_agg['count'] / max_count

    ds = hv.Dataset(data=df_agg, kdims=['time', 'amount'], vdims=['normalized_count'])
    heatmap = ds.to(hv.HeatMap, ['time', 'amount'], 'normalized_count')

    labels = get_graph_labels("", metric)
    heatmap.opts(opts.HeatMap(
        **labels,
        tools=["hover"],
        colorbar=True,
        width=800,
        toolbar="above",
        cmap='Blues')
    )

    filename = output_dir + metric + "_heatmap.html"
    hv.render(heatmap)
    hv.save(heatmap, filename)

    if show:
        webbrowser.open(filename)


def generate_pairplot(data: List[dict[str, Any]], metric1: str, metric2: str, show: bool) -> None:
    """Generate a pairplot Matrix (SPLOM) for exploring relationships between multiple metrics in the given dataset.
       https://seaborn.pydata.org/generated/seaborn.pairplot.html

    Parameters:
        data (List[dict[str, Any]]): The dataset as a list of dictionaries.
        metric1 (str): The first metric to be compared.
        metric2 (str): The second metric to be compared.
        show (bool): Flag indicating whether to display the pairplot or not.

    Returns:
        None
    """

    df = pd.DataFrame(data)

    sns.set(style="ticks", color_codes=True)

    filtered_memory_df = df[df["type"] == metric1].copy()
    filtered_latency_df = df[df["type"] == metric2].copy()

    filtered_memory_df.reset_index(drop=True, inplace=True)
    filtered_latency_df.reset_index(drop=True, inplace=True)

    combined_df = pd.DataFrame({
        "memory_amount [B]": filtered_memory_df["amount"],
        "latency_amount [ms]": filtered_latency_df["amount"]
    })

    sns.pairplot(combined_df)

    if show:
        plt.show()

    plt.savefig(f"{output_dir}pairplot_memory_latency.png")


def get_graph_labels(route, metric) -> Union[dict[str, str], None]:
    """Function for graph labels for supported metrics.

    Args:
        route (str): The route for which labels are needed.
        metric (str): The metric for which labels are needed.

    Returns:
        Union[Dict[str, str], None]: A dictionary containing graph labels if supported, otherwise None.
    """
    match metric:
        case "page_requests":
            plt.xlabel("Time")
            plt.ylabel(f"Number of requests")
            plt.title(f"Number of requests over time - Route {route}")
        case "error_count":
            plt.xlabel("Time")
            plt.ylabel(f"Number of errors")
            plt.title(f"Number of errors for route {route}")
        case "memory_usage_counter":
            return {'xlabel': 'Time [hh:mm:ss]', 'ylabel': 'Memory used [B]', 'title': 'Memory heatmap'}
        case "request_latency_summary":
            return {'xlabel': 'Time [hh:mm:ss]', 'ylabel': 'Page Latency [ms]', 'title': 'Latency heatmap'}
        case _:
            raise UnsupportedMetricException("Labels for this metric are not specified")


def generate_line_graph(data: List[dict[str, Any]], group_by: str, metric: str, show: bool) -> None:
    """Generate line graph for metrics without unit. Plot graph for number of occurrences.
    You need to define labels for new metric in `get_graph_labels`, if it is not done already.

    Args:
        data (List[Dict[str, Any]]): The data to be plotted.
        group_by (str): The time interval for grouping the data.
        metric (str): The metric to be visualized.
        show (bool): Whether to display the line graph.

    Returns:
        None
    """
    df = pd.DataFrame(data)
    df.drop(columns=["time"], inplace=True)
    df.rename(columns={"amount": "value"}, inplace=True)
    df = df[df["type"] == metric]
    df = df[df["uid"] != "/favicon.ico"]

    os.makedirs(output_dir, exist_ok=True)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["time_grouped"] = df["timestamp"].dt.floor(group_by)
    grouped_df = df.set_index("timestamp").groupby("uid").resample(group_by).size().reset_index(name="requests")

    for route, route_data in grouped_df.groupby("uid"):
        plt.figure(figsize=(10, 6))

        route_data["timestamp"] = route_data["timestamp"].dt.strftime("%H:%M:%S")
        plt.plot(route_data["timestamp"], route_data["requests"], label=route)
        plt.fill_between(route_data["timestamp"], route_data["requests"], color="skyblue", alpha=0.4)

        get_graph_labels(route, metric)

        plt.xticks(rotation=30)
        plt.tight_layout()

        if not route == "/":
            filename = f"{output_dir}{metric}_{route.lstrip('/')}.png"
        else:
            filename = f"{output_dir}{metric}_root.png"

        plt.savefig(filename)

        if show:
            plt.show()

        plt.close()


def run_call_graph() -> None:
    """Generates simple call graph of functions of project
    Function finds all TS files in project and statically find project functions
    to create call graph.
    Credits to author of the package https://github.com/whyboris/TypeScript-Call-Graph

    Returns:
        None
    """

    find_command = "find . -type f -name '*.ts'"
    find_process = subprocess.Popen(find_command, stdout=subprocess.PIPE, shell=True)
    ts_files, _ = find_process.communicate()
    ts_files = ts_files.decode().strip().split("\n")

    printf_command = "printf 'y\n'"
    npx_tcg_command = f"npx tcg {' '.join(shlex.quote(file) for file in ts_files)}"

    process_printf = subprocess.Popen(printf_command, stdout=subprocess.PIPE, shell=True)
    subprocess.Popen(npx_tcg_command, stdin=process_printf.stdout, shell=True)


@click.command()
@click.option(
    "--group-by",
    "-g",
    default="1min",
    required=False,
    help="Group by values in graphs by time span\n"
         "For example group values by:"
         "`5s`   - 5 seconds"
         "`1min` - 1 minute"
         "1h     - 1 hour"
         "1D     - 1 day"
)
@click.option(
    "--show",
    "-s",
    default=False,
    required=False,
    is_flag=True,
    help="Show generated graphs and call graph."
         "Graphs will be saved in any case to current directory."
)
@profile_factory.pass_profile
def web(profile: profile_factory.Profile, group_by: str, show: bool) -> None:
    """Graphs visualizing metrics collected by web collector.
       Graphs are saved to /view directory in your project

       Returns:
           None
    """

    data = profile.all_resources()
    sliced_data = [item[1] for item in data]

    generate_line_graph(sliced_data, group_by, "page_requests", show)
    generate_line_graph(sliced_data, group_by, "error_count", show)

    generate_pairplot(sliced_data, "memory_usage_counter", "request_latency_summary", show)

    generate_heatmap(sliced_data, "memory_usage_counter", show)
    generate_heatmap(sliced_data, "request_latency_summary", show)

    # generate_psutil(sliced_data, "memory_usage_counter", show)

    if show and False:
        run_call_graph()
