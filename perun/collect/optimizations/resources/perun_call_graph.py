""" The extraction and storage methods for the internal Perun call graph format. While
angr call graph provider extracts the call graph from a binary file or the current project version,
the Perun call graph provider handles storage of the internal call graph format in the 'stats'
and loading call graphs from previous project versions.
"""


import perun.logic.temp as temp
import perun.logic.stats as stats
from perun.utils.helpers import SuppressedExceptions
from perun.utils.exceptions import StatsFileNotFoundException


def extract(stats_name, **_):
    """ Load the call graph of latest previous version that has the file stored in 'stats'.

    :param str stats_name: name of the call graph file

    :return dict: the internal Perun call graph format
    """
    return stats.get_latest(stats_name, ['perun_cg'], exclude_self=True).get('perun_cg', {})


def store(stats_name, call_graph, cache, **_):
    """ Store the internal call graph structure into the 'stats' directory

    :param str stats_name: name of the stats file
    :param CallGraphResource call_graph: the internal call graph format
    :param bool cache: sets the cache on / off configuration
    """
    if cache:
        # Do not save the file again if it already exists
        with SuppressedExceptions(StatsFileNotFoundException):
            stats.get_stats_file_path(stats_name, check_existence=True)
            return

    serialized = {
        'call_graph': {
            'cg_map': call_graph.cg_map,
            'levels': call_graph.levels,
            'leaves': call_graph.leaves,
            'recursive': list(call_graph.recursive),
            'depth': call_graph.depth
        },
        'control_flow': call_graph.cfg,
        'minor_version': call_graph.minor
    }
    stats.add_stats(stats_name, ['perun_cg'], [serialized])
    temp.store_temp('optimization/call_graph.json', serialized, json_format=True)
