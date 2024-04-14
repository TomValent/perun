"""Graphical visualization of the profiles made by `web` collector"""

import os
import click
import shlex
import subprocess
import webbrowser
import pandas as pd
import seaborn as sns
import holoviews as hv
import perun.profile.factory as profile_factory

from holoviews import opts
from typing import Any, List, Union, Dict
from matplotlib import pyplot as plt
from perun.utils import log as perun_log
from matplotlib.colors import LinearSegmentedColormap
from perun.view.web.unsupported_metric_exception import UnsupportedMetricException


output_dir = "view/"


def generate_heatmap(data: List[dict[str, Any]], metric: str, show: bool, group_by: str = "2min") -> None:
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
    df["count"] = 1

    df_filtered = df[df["type"] == metric]
    df_agg = df_filtered.groupby(["time", "amount"]).count().reset_index()

    max_count = df_agg["count"].max()
    df_agg["normalized_count"] = df_agg["count"] / max_count

    ds = hv.Dataset(data=df_agg, kdims=["time", "amount"], vdims=["normalized_count"])
    heatmap = ds.to(hv.HeatMap, ["time", "amount"], "normalized_count")

    cmap = ["black", "red", "orange", "yellow"]
    cmap = LinearSegmentedColormap.from_list("cmap", cmap)
    labels = get_graph_labels("", metric)
    heatmap.opts(
        opts.HeatMap(
            **labels,
            tools=["hover"],
            colorbar=True,
            width=800,
            toolbar="above",
            cmap=cmap,
        )
    )

    filename = output_dir + metric + "_heatmap.html"
    hv.render(heatmap)
    hv.save(heatmap, filename)

    if show:
        webbrowser.open(filename)


def get_pairplot_labels(metric: str, data: Any) -> Dict[str, Any]:
    """Generate pairplot labels for the given metric and data.

    Parameters:
        metric (str): The metric for which labels are to be generated.
        data (Any): The data associated with the metric.

    Returns:
        Dict[str, Any]: A dictionary containing pairplot labels for the given metric and data.
    """

    match metric:
        case "memory_usage_counter":
            return {"Memory_amount (MB)": data}
        case "request_latency_summary":
            return {"Latency amount (ms)": data}
        case "user_cpu_usage":
            return {"User CPU Usage (s)": data}
        case "system_cpu_usage":
            return {"System CPU Usage (s)": data}
        case "user_cpu_time":
            return {"User CPU Time (s)": data}
        case "system_cpu_time":
            return {"System CPU Time (s)": data}
        case "fs_read":
            return {"FS Read": data}
        case "fs_write":
            return {"FS Write": data}
        case "voluntary_context_switches":
            return {"Voluntary Context Switches": data}
        case _:
            raise UnsupportedMetricException("Labels for this metric are not specified")


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

    filtered_df_metric1 = df[df["type"] == metric1].copy()
    filtered_df_metric2 = df[df["type"] == metric2].copy()

    filtered_df_metric1.reset_index(drop=True, inplace=True)
    filtered_df_metric2.reset_index(drop=True, inplace=True)

    combined_df = pd.DataFrame({
        get_pairplot_labels(metric1, filtered_df_metric1["amount"]),
        get_pairplot_labels(metric2, filtered_df_metric2["amount"]),
    })

    sns.set(rc={'figure.figsize': (10, 10)})
    pairplot = sns.pairplot(combined_df)

    if show:
        plt.show()

    pairplot.savefig(f"{output_dir}pairplot_{metric1}_{metric2}.png")


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
            plt.ylabel("Number of requests")
            plt.title(f"Number of requests over time - Route {route}")
        case "error_count":
            plt.xlabel("Time")
            plt.ylabel("Number of errors")
            plt.title(f"Number of errors for route {route}")
        case "memory_usage_counter":
            return {"xlabel": "Time [hh:mm:ss]", "ylabel": "Memory used [MB]", "title": "Memory heatmap"}
        case "request_latency_summary":
            return {"xlabel": "Time [hh:mm:ss]", "ylabel": "Page Latency [ms]", "title": "Latency heatmap"}
        case "fs_read":
            plt.xlabel("Time")
            plt.ylabel("File system reads")
            plt.title(f"Number of fs reads over time for all routes")
        case "fs_write":
            plt.xlabel("Time")
            plt.ylabel("File system writes")
            plt.title(f"Number of fs writes over time for all routes")
        case "voluntary_context_switches":
            plt.xlabel("Time")
            plt.ylabel("Voluntary context switches")
            plt.title(f"Number of voluntary context switches over time for all routes")
        case _:
            raise UnsupportedMetricException("Labels for this metric are not specified")


def generate_line_graph(
        data: List[dict[str, Any]],
        group_by: str,
        metric: str,
        show: bool,
        for_all_routes: bool = False
) -> None:
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

    if for_all_routes:
        plt.figure(figsize=(10, 6))

        summed_requests = grouped_df.groupby("timestamp")["requests"].sum().reset_index()

        summed_requests["timestamp"] = summed_requests["timestamp"].dt.strftime("%H:%M:%S")
        plt.plot(summed_requests["timestamp"], summed_requests["requests"])
        plt.fill_between(summed_requests["timestamp"], summed_requests["requests"], color="skyblue", alpha=0.4)

        get_graph_labels("", metric)

        plt.xticks(rotation=30)
        plt.tight_layout()

        filename = f"{output_dir}{metric}_all_routes.png"

        plt.savefig(filename)

        if show:
            plt.show()

        plt.close()

    else:
        for route, route_data in grouped_df.groupby("uid"):
            plt.figure(figsize=(10, 6))

            route_data["timestamp"] = route_data["timestamp"].dt.strftime("%H:%M:%S")
            plt.plot(route_data["timestamp"], route_data["requests"], label=route)
            plt.fill_between(route_data["timestamp"], route_data["requests"], color="skyblue", alpha=0.4)

            get_graph_labels(route, metric)

            plt.xticks(rotation=30)
            plt.tight_layout()

            if not route == "/":
                filename = f"{output_dir}{metric}_{route.lstrip('/').replace('/', '_')}.png"
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

    perun_log.minor_info("Parsing profile for graphs...")

    data = profile.all_resources()
    sliced_data = [item[1] for item in data]

    perun_log.minor_info("Generating graphs...")

    # generate_line_graph(sliced_data, group_by, "page_requests", show)
    # generate_line_graph(sliced_data, group_by, "fs_read", show, True)
    # generate_line_graph(sliced_data, group_by, "fs_write", show, True)
    # generate_line_graph(sliced_data, group_by, "voluntary_context_switches", show, True)

    # generate_pairplot(sliced_data, "memory_usage_counter", "request_latency_summary", show)
    generate_pairplot(sliced_data, "fs_read", "fs_write", show)
    generate_pairplot(sliced_data, "user_cpu_usage", "user_cpu_time", show)
    generate_pairplot(sliced_data, "user_cpu_time", "system_cpu_time", show)
    generate_pairplot(sliced_data, "voluntary_context_switches", "system_cpu_time", show)

    # generate_heatmap(sliced_data, "memory_usage_counter", show, group_by)
    # generate_heatmap(sliced_data, "request_latency_summary", show, group_by)
    #
    # if show:
    #     perun_log.minor_info("Generating call graph...")
    #     perun_log.minor_info("This call graph works for typescript files only...")
    #     run_call_graph()

    perun_log.minor_info("Generating graphs finished...")
