"""Wrapper for web collector, which collects profiling data from
TypeScript/JavaScript web applications

Specifies before, collect, after and teardown functions to perform the initialization,
collection and postprocessing of collection data.
"""
import json
import click
import subprocess

from typing import Any
from perun.collect.trace.strategy import extract_configuration
from perun.utils import log as perun_log
from perun.collect.trace.configuration import Configuration
from perun.collect.trace.values import (
    check,
    GLOBAL_DEPENDENCIES,
)

import perun.logic.runner as runner
import perun.utils.metrics as metrics
from perun.utils.structs import CollectStatus


@click.command()
@click.option(
    "--path",
    "-p",
    type=str,
    required=True,
    default="",
    help="Path to your project to profile"
)
@click.option(
    "--command",
    "-c",
    type=str,
    required=True,
    default="start",
    help="Script name to start your project.\n"
         "For example: 'start' => 'yarn start'"
)
def before(executable, **kwargs):
    """Validates, initializes and normalizes the collection configuration.

    :param Executable executable: full collection command with arguments and workload
    :param kwargs: dictionary containing the supplied configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """

    perun_log.minor_info("Pre-processing phase...")

    # Check if we run in a workload generator batch and update metrics accordingly
    if executable.workload != executable.origin_workload:
        metrics.Metrics.add_sub_id(executable.workload)

    project_path = kwargs["path"]
    command = kwargs["command"]

    try:
        subprocess.run(["yarn", command], cwd=project_path)
    except subprocess.CalledProcessError as e:
        perun_log.error(f"Could not execute start command: yarn {command}")

    # Validate and normalize collection parameters
    config = Configuration(executable, **kwargs)

    kwargs["opened_resources"].append(config)
    kwargs["config"] = config
    kwargs["probes"] = config.probes
    config.engine_factory()

    # Check all the required dependencies
    check(GLOBAL_DEPENDENCIES)
    config.engine.check_dependencies()

    # Extract and / or post-process the collect configuration
    extract_configuration(config.engine, kwargs["probes"])
    if not kwargs["probes"].func and not kwargs["probes"].usdt:
        msg = (
            "No profiling probes created (due to invalid specification, failed extraction or "
            "filtering)"
        )
        return CollectStatus.ERROR, msg, dict(kwargs)

    # Set the variables for optimization methods
    kwargs["binary"] = config.binary

    # Cleanup the kwargs and log all the dictionaries
    perun_log.minor_info("before::kwargs", json.dumps(kwargs))
    perun_log.minor_info("before::kwargs::config", json.dumps(config.__dict__))
    perun_log.minor_info("before::kwargs::probes", kwargs["probes"].__dict__)

    return CollectStatus.OK, "", dict(kwargs)


@click.command()
@click.option(
    "--path",
    "-p",
    type=str,
    required=True,
    default="",
    help="Path to OpenTelemetry profiler script"
)
def collect(**kwargs):
    """Assembles the engine collect program according to input parameters and collection strategy.
    Runs the created collection program and the profiled command.

    :param kwargs: dictionary containing the configuration and probe settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """

    perun_log.minor_info("Collect phase...")
    config = kwargs["config"]

    metrics.add_metric("page_requests", 0)
    metrics.add_metric("error_count", 0)
    metrics.add_metric("error_code_count", 0)
    metrics.add_metric("error_message_count", 0)
    metrics.add_metric("memory_usage_counter", 0)
    metrics.add_metric("request_latency_summary", 0)

    profiler_path = kwargs["path"]
    command = "start"

    try:
        subprocess.run(["yarn", command], cwd=profiler_path)
    except subprocess.CalledProcessError as e:
        perun_log.error(f"Could not execute start command: yarn {command}")

    # Assemble the collection program according to the parameters
    metrics.add_metric("func_count", len(config.probes.func.keys()))
    config.engine.assemble_collect_program(**kwargs)

    return CollectStatus.OK, "", dict(kwargs)


def after(**kwargs):
    """Parses the trace collector output and transforms it into profile resources

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    perun_log.minor_info("Post-processing phase... ")



    perun_log.minor_info("Data processing finished.")

    return CollectStatus.OK, "", dict(kwargs)


def teardown(**kwargs):
    """Perform a cleanup of all the collection resources that need it, i.e. files, locks,
    processes, kernel modules etc.

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    perun_log.minor_info("Teardown phase...")

    # The Configuration object can be directly in kwargs or the resources list
    config = None
    if "config" in kwargs:
        config = kwargs["config"]
    elif kwargs["opened_resources"]:
        config = kwargs["opened_resources"][0]
        kwargs["config"] = config

    # Cleanup all the engine related resources
    # Check that the engine was actually constructed
    if config is not None and not isinstance(config.engine, str):
        config.engine.cleanup(**kwargs)

    return CollectStatus.OK, "", dict(kwargs)


@click.command()
def web(ctx: click.Context, **kwargs: Any) -> None:
    """Generates `web` performance profile, capturing different metrics such as latency, request
    count or errors occurrences
    """
    runner.run_collector_from_cli_context(ctx, "web", kwargs)
