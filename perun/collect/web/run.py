"""Wrapper for web collector, which collects profiling data from
TypeScript/JavaScript web applications

Specifies before, collect, after and teardown functions to perform the initialization,
collection and postprocessing of collection data.
"""

import os
import click
import psutil
import requests
import subprocess
import perun.logic.runner as runner

from time import sleep
from typing import Any, List
from datetime import datetime
from perun.utils import log as perun_log
from perun.utils.external import processes
from perun.collect.web.parser import Parser
from perun.utils.structs import CollectStatus, Executable
from perun.collect.web.build_exception import BuildException


def before(executable: Executable, **kwargs):
    """Validates, initializes and normalizes the collection configuration.

    :param Executable executable: full collection command with arguments and workload
    :param kwargs: dictionary containing the supplied configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """

    perun_log.minor_info("Pre-processing phase...")
    perun_log.minor_info("Checking if target project is built...")

    project_path = kwargs["proj"]
    kwargs["prof_port"] = 9000

    build_dir = os.path.join(project_path, "build")
    dist_dir = os.path.join(project_path, "dist")
    out_dir = os.path.join(project_path, "out")

    if not os.path.exists(build_dir) and not os.path.exists(dist_dir) and not os.path.exists(out_dir):
        raise BuildException(
            "Build directory does not, please build your application before profiling.\n"
            "Supported build directories are 'build', 'dist', 'out'\n"
        )

    return CollectStatus.OK, "", dict(kwargs)


def collect(**kwargs):
    """Assembles the engine collect program according to input parameters and collection strategy.
    Runs the created collection program and the profiled command.

    :param kwargs: dictionary containing the configuration and probe settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """

    project_path = kwargs["proj"]
    index_file = kwargs["index"]
    timeout = kwargs["timeout"]
    project_port = kwargs["port"]
    profiler_port = kwargs["prof_port"]
    profiler_path = kwargs["otp"]
    command = "start"

    with processes.nonblocking_subprocess(
            "yarn " + command + " --silent " + "--path " + project_path + index_file,
            {"cwd": profiler_path}
    ) as prof_process:
        perun_log.minor_info("Warm up phase...")
        server_url = "http://localhost:" + str(project_port)
        if wait_until_server_starts(server_url):
            perun_log.minor_info("Collect phase...")

            sleep(timeout)
            kill_processes([project_port, profiler_port])

            perun_log.minor_info("Collecting finished...")
        else:
            perun_log.error("Could not start profiler or target project...")

    return CollectStatus.OK, "", dict(kwargs)


def kill_processes(ports: List[int]) -> None:
    """Terminate processes listening on specified ports after timeout.

    :param ports: List of integers representing ports on which processes are running.
    :return: None
    """

    for port in ports:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                subprocess.run(["kill", "-9", str(conn.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_until_server_starts(url: str, max_attempts: int = 20, wait_time: float = 0.5) -> bool:
    """Wait until a server at the specified URL starts responding.

    :param url: The URL of the server to wait for.
    :param max_attempts: The maximum number of attempts to make before giving up. Default is 10.
    :param wait_time: The time to wait (in seconds) between attempts. Default is 1.
    :return: True if the server started within the specified attempts, False otherwise.
    """

    for _ in range(max_attempts):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        sleep(wait_time)
    return False


def after(**kwargs):
    """Parses the trace collector output and transforms it into profile resources

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    perun_log.minor_info("Post-processing phase... ")

    log_dir = kwargs["otp"]
    metrics = os.path.join(log_dir, "data/metrics/metrics.log")
    done_folder = os.path.join(log_dir, "data/metrics/done")
    os.makedirs(done_folder, exist_ok=True)

    metrics_data = []
    parser = Parser()

    try:
        with open(metrics, 'r') as metrics_file:
            for line in metrics_file:
                parsed_line = parser.parse_metric(line)
                metrics_data.append(parsed_line)
            os.rename(metrics, os.path.join(done_folder, "metrics.log"))
    except FileNotFoundError as e:
        perun_log.error(f"File {metrics} was not created or cannot be opened")
        exit(1)

    perun_log.minor_info("Data processing finished.")

    return (
        CollectStatus.OK,
        "",
        {
            "profile": {
                "global": {
                    "timestamp": datetime.now().timestamp(),
                    "resources": [
                        {
                            "amount": value,
                            "uid": route,
                            "type": key,
                        }
                        for (key, value, route) in metrics_data
                    ]
                }
            }
        }
    )


def teardown(**kwargs):
    """Perform a cleanup of all the collection resources that need it, i.e. files, locks,
    processes, kernel modules etc.

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    perun_log.minor_info("Teardown phase...")

    kill_processes([kwargs["port"], kwargs["prof_port"]])

    return CollectStatus.OK, "", dict(kwargs)


@click.command()
@click.option(
    "--otp",
    "-o",
    type=str,
    required=True,
    default="",
    help="Path to the OpenTelemetry profiler script"
)
@click.option(
    "--proj",
    "-p",
    type=str,
    required=True,
    default="",
    help="Path to the project to be profiled"
)
@click.option(
    "--index",
    "-i",
    type=str,
    required=True,
    default="src/index",
    help="Path to index file in your project\n"
         "Alternatively you can specify other main file"
)
@click.option(
    "--port",
    type=int,
    required=True,
    help="Port on which project run"
)
@click.option(
    "--timeout",
    "-t",
    type=int,
    required=False,
    default=60,
    help="Timeout for the runtime of profiling in seconds"
)
@click.pass_context
def web(ctx: click.Context, **kwargs: Any) -> None:
    """Generates `web` performance profile, capturing different metrics such as latency, request
    count or errors occurrences
    """
    runner.run_collector_from_cli_context(ctx, "web", kwargs)
