"""Graphical visualization of the profiles made by `web` collector"""

import os
import click
import shlex
import subprocess
import pandas as pd
import perun.profile.factory as profile_factory

from typing import Any, List
from matplotlib import pyplot as plt
from perun.view.web.unsupported_metric_exception import UnsupportedMetricException


def get_graph_labels(route, metric):
    match metric:
        case "page_requests":
            plt.xlabel("Time")
            plt.ylabel(f"Number of requests")
            plt.title(f"Number of requests over time - Route {route}")
        case "error_count":
            plt.xlabel("Time")
            plt.ylabel(f"Number of errors")
            plt.title(f"Number of errors for route {route}")
        case _:
            raise UnsupportedMetricException("Labels for this metric are not specified")


def generate_line_graph(data: List[dict[str, Any]], group_by: str, metric: str, show: bool):
    """Generate line graph for metrics without unit. Plot graph for number of occurrences
    """
    df = pd.DataFrame(data)
    df.drop(columns=["time"], inplace=True)
    df.rename(columns={"amount": "value"}, inplace=True)
    df = df[df["type"] == metric]
    df = df[df["uid"] != "/favicon.ico"]
    print(df)

    output_dir = os.path.join(os.getcwd(), 'view')
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

        filename = f"{output_dir}/{metric}_{route.lstrip('/')}.png"
        plt.savefig(filename)

        if show:
            plt.show()

        plt.close()


def run_call_graph():
    """Generates simple call graph of functions of project
    Function finds all TS files in project and statically find project functions
    to create call graph.
    Credits to author of the package https://github.com/whyboris/TypeScript-Call-Graph
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
    """

    data = profile.all_resources()
    sliced_data = [item[1] for item in data]

    generate_line_graph(sliced_data, group_by, "page_requests", show)
    generate_line_graph(sliced_data, group_by, "error_count", show)

    if show:
        run_call_graph()
