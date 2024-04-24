"""Sankey difference of the profiles

The difference is in form of:

cmd       | cmd
workload  | workload
collector | kernel

| ---\          /======|
     |-----|====
|---/          \------|

"""
from __future__ import annotations

# Standard Imports
from operator import itemgetter
from typing import Any, Literal, Type, Callable
from collections import defaultdict
from dataclasses import dataclass

# Third-Party Imports
import click
import jinja2
import progressbar

# Perun Imports
from perun.profile import convert
from perun.profile.factory import Profile
from perun.utils import log
from perun.utils.common import diff_kit, common_kit
from perun.view_diff.flamegraph import run as flamegraph_run


def singleton_class(cls: Type) -> Callable[[], Config]:
    """Helper class for creating singleton objects"""
    instances = {}

    def getinstance() -> Config:
        """Singleton instance"""
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return getinstance


@singleton_class
class Config:
    """Singleton config for generation of sankey graphs

    :ivar trace_is_inclusive: if set to true, then the amounts are distributed among the whole traces
    """

    def __init__(self):
        """Initializes the config

        By default we consider, that the traces are not inclusive
        """
        self.trace_is_inclusive: bool = False


class ColorPalette:
    """Colour palette is a static object for grouping colours used in visualizations"""

    Baseline: str = "rgba(49, 48, 77, 0.4)"
    Target: str = "rgba(255, 201, 74, 0.4)"
    NotInBaseline: str = "rgba(255, 0, 0, 0.4)"
    NotInTarget: str = "rgba(0, 255, 0, 0.4)"
    InBoth: str = "rgba(0, 0, 255, 0.4)"
    Highlight: str = "rgba(0, 0, 0, 0.7)"
    NoHighlight: str = "rgba(0, 0, 0, 0.2)"


@dataclass
class SelectionRow:
    """Helper dataclass for displaying selection of data

    :ivar uid: uid of the selected graph
    :ivar index: index in the sorted list of data
    :ivar abs_amount: absolute change in the units
    :ivar rel_amount: relative change in the units
    """

    __slots__ = ["uid", "index", "abs_amount", "rel_amount"]
    uid: str
    index: int
    abs_amount: float
    rel_amount: float


class Graph:
    """Represents single sankey graph

    :ivar nodes: mapping of uids#pos to concrete sankey nodes
    :ivar uid_to_nodes: mapping of uid to list of its uid#pos, i.e. uid in different contexts
    :ivar uid_to_id: mapping of uid to unique identifiers
    :ivar stats_to_id: mapping of stats to unique identifiers
    """

    __slots__ = ["nodes", "uid_to_nodes", "uid_to_id", "stats_to_id"]

    nodes: dict[str, Node]
    uid_to_nodes: dict[str, list[Node]]
    uid_to_id: dict[str, int]
    stats_to_id: dict[str, int]

    def __init__(self):
        """Initializes empty graph"""
        self.nodes = {}
        self.uid_to_nodes = defaultdict(list)
        self.stats_to_id = {}
        self.uid_to_id = {}

    def get_node(self, node: str) -> Node:
        """For give uid#pos returns its corresponding node

        If the uid is not yet assigned unique id, we assign it.
        If the node has corresponding node created we return it.

        :param node: node in form of uid#pos
        :return: corresponding node in sankey graph
        """
        uid = node.split("#")[0]
        if uid not in self.uid_to_id:
            self.uid_to_id[uid] = len(self.uid_to_id)
        if node not in self.nodes:
            self.nodes[node] = Node(node)
            self.uid_to_nodes[uid].append(self.nodes[node])
        return self.nodes[node]

    def translate_stats(self, stats: str) -> int:
        """Translates string representation of stats to unique id

        :param stats: stats represented as string
        :return: unique id for the string
        """
        if stats not in self.stats_to_id:
            self.stats_to_id[stats] = len(self.stats_to_id)
        return self.stats_to_id[stats]

    def translate_node(self, node) -> str:
        """Translates the node to its unique id

        :param node: node which we are translating to id
        :return: unique identifier for the node uid
        """
        if "#" in node:
            return f"{self.uid_to_id[node.split('#')[0]]}"
        return str(self.uid_to_id[node])

    def get_pred_stats(self, src: str, tgt: str) -> Stats:
        """Returns stats for predecessors of the src

        :param src: source node
        :param tgt: target predecessor node
        :return: stats
        """
        # Create node if it does not already exist
        src_node = self.get_node(src)

        # Get link if it does not already exist
        if tgt not in src_node.preds:
            tgt_node = self.get_node(tgt)
            src_node.preds[tgt] = Link(tgt_node, Stats())

        return src_node.preds[tgt].stats

    def get_succ_stats(self, src: str, tgt: str) -> Stats:
        """Returns stats for successors of the src

        :param src: source node
        :param tgt: target successor node
        :return: stats
        """
        # Create node if it does not already exist
        src_node = self.get_node(src)

        # Get link if it does not already exist
        if tgt not in src_node.succs:
            tgt_node = self.get_node(tgt)
            src_node.succs[tgt] = Link(tgt_node, Stats())

        return src_node.succs[tgt].stats

    def to_jinja_string(self, link_type: Literal["succs", "preds"] = "succs") -> str:
        """Since jinja seems to be awfully slow with this, we render the result ourselves

        1. Target nodes of "uid#pos" are simplified to "uid", since you can infer pos to be pos+1 of source
        2. Stats are merged together: first half is for baseline, second half is for target

        TODO: switch preds to callers and succs to callees

        :param link_type: either succs for successors or pred for predecessors
        :return string representation of the successor or predecessor relation
        """

        def comma_control(commas: list[bool], pos: int) -> str:
            """Helper function for comma control

            :param pos: position in the nesting
            :param commas: list of boolean flags for comma control (true = we should output)
            """
            if commas[pos]:
                return ","
            commas[pos] = True
            return ""

        output = "{"
        commas = [False, False, False]
        for uid, nodes in progressbar.progressbar(self.uid_to_nodes.items()):
            output += comma_control(commas, 0) + f"{self.translate_node(uid)}:" + "{"
            commas[1] = False
            for node in nodes:
                output += comma_control(commas, 1) + f"{node.get_order()}:" + "{"
                commas[2] = False
                for link in node.get_links(link_type).values():
                    assert link_type == "preds" or int(node.get_order()) + 1 == int(
                        link.target.get_order()
                    )
                    assert (
                        link_type == "succs"
                        or int(node.get_order()) == int(link.target.get_order()) + 1
                    )
                    output += comma_control(commas, 2) + f"{self.translate_node(link.target.uid)}:"
                    stats = f"[{','.join(link.stats.to_array('baseline') + link.stats.to_array('target'))}]"
                    output += str(self.translate_stats(stats))
                output += "}"
            output += "}"
        output += "}"
        return output


@dataclass
class Node:
    """Single node in sankey graph

    :ivar uid: unique identifier of the node (the label)
    :ivar succs: mapp of positions to edge relation for successors
    :ivar preds: mapp of positions to edge relation for predecessors
    """

    __slots__ = ["uid", "succs", "preds"]

    uid: str
    succs: dict[str, Link]
    preds: dict[str, Link]

    def __init__(self, uid: str):
        """Initializes the node"""
        self.uid = uid
        self.succs = {}
        self.preds = {}

    def get_links(self, link_type: Literal["succs", "preds"]) -> dict[str, Link]:
        """Returns linkage based on given type

        :param link_type: either successors or predecessors
        :return: linkage of the given ty pe
        """
        if link_type == "succs":
            return self.succs
        assert link_type == "preds"
        return self.preds

    def get_order(self) -> int:
        """Gets position/order in the call traces

        :return: order/position in the call traces
        """
        return int(self.uid.split("#")[1])


@dataclass
class Link:
    """Helper dataclass for linking two nodes

    :ivar target: target of the edge
    :ivar stats: stats of the edge
    """

    __slots__ = ["stats", "target"]
    target: Node
    stats: Stats


class Stats:
    """Statistics for a given edge

    :ivar baseline: baseline stats
    :ivar target: target stats
    """

    __slots__ = ["baseline", "target"]
    KnownStats: set[str] = set()

    def __init__(self):
        """Initializes the stat"""
        self.baseline: dict[str, float] = defaultdict(float)
        self.target: dict[str, float] = defaultdict(float)

    def add_stat(
        self, stat_type: Literal["baseline", "target"], stat_key: str, stat_val: int | float
    ) -> None:
        """Adds stat of given type

        :ivar stat_type: type of the stat (either baseline or target)
        :ivar stat_key: type of the metric
        :ivar stat_val: value of the metric
        """
        Stats.KnownStats.add(stat_key)
        if stat_type == "baseline":
            self.baseline[stat_key] += stat_val
        else:
            self.target[stat_key] += stat_val

    def to_array(self, stat_type: Literal["baseline", "target"]) -> list[str]:
        """Converts stats to single compact array"""
        # TODO: Add different type for int/float
        stats = self.baseline if stat_type == "baseline" else self.target
        return [
            common_kit.compact_convert_num_to_str(stats.get(stat, 0), 2)
            for stat in Stats.KnownStats
        ]


def process_edge(
    graph: Graph,
    profile_type: Literal["baseline", "target"],
    resource: dict[str, Any],
    src: str,
    tgt: str,
) -> None:
    """Processes single edge with given resources

    :param graph: sankey graph
    :param profile_type: type of the profile
    :param resource: consumed resources
    :param src: caller
    :param tgt: callee
    """
    src_stats = graph.get_succ_stats(src, tgt)
    tgt_stats = graph.get_pred_stats(tgt, src)
    for key in resource:
        amount = common_kit.try_convert(resource[key], [float])
        if amount is None:
            continue
        src_stats.add_stat(profile_type, key, amount)
        tgt_stats.add_stat(profile_type, key, amount)


def process_traces(
    profile: Profile, profile_type: Literal["baseline", "target"], graph: Graph
) -> None:
    """Processes all traces in the profile

    Iterates through all traces and creates edges for each pair of source and target.

    :param profile: input profile
    :param profile_type: type of the profile
    :param graph: sankey graph
    """
    for _, resource in progressbar.progressbar(profile.all_resources()):
        full_trace = [convert.to_uid(t) for t in resource["trace"]] + [
            convert.to_uid(resource["uid"])
        ]
        trace_len = len(full_trace)
        if trace_len > 1:
            if Config().trace_is_inclusive:
                for i in range(0, trace_len - 1):
                    src = f"{full_trace[i]}#{i}"
                    tgt = f"{full_trace[i+1]}#{i+1}"
                    process_edge(graph, profile_type, resource, src, tgt)
            else:
                src = f"{full_trace[-2]}#{trace_len-2}"
                tgt = f"{full_trace[-1]}#{trace_len-1}"
                process_edge(graph, profile_type, resource, src, tgt)


def generate_sankey_difference(lhs_profile: Profile, rhs_profile: Profile, **kwargs: Any) -> None:
    """Generates differences of two profiles as sankey diagram

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: additional arguments
    """
    # We automatically set the value of True for kperf, which samples
    if lhs_profile.get("collector_info", {}).get("name") == "kperf":
        Config().trace_is_inclusive = True

    log.major_info("Generating Sankey Graph Difference")

    graph = Graph()

    process_traces(lhs_profile, "baseline", graph)
    process_traces(rhs_profile, "target", graph)

    selection_table = [SelectionRow(uid, graph.uid_to_id[uid], 0, 0) for uid in graph.uid_to_nodes]
    log.minor_success("Sankey graphs", "generated")

    env = jinja2.Environment(loader=jinja2.PackageLoader("perun", "templates"))
    template = env.get_template("diff_view_sankey_incremental.html.jinja2")
    content = template.render(
        title="Differences of profiles (with sankey)",
        lhs_tag="Baseline (base)",
        lhs_header=flamegraph_run.generate_header(lhs_profile),
        rhs_tag="Target (tgt)",
        rhs_header=flamegraph_run.generate_header(rhs_profile),
        palette=ColorPalette,
        succ_graph=graph.to_jinja_string("succs"),
        pred_graph=graph.to_jinja_string("preds"),
        stats="["
        + ",".join(
            list(map(itemgetter(0), sorted(list(graph.stats_to_id.items()), key=itemgetter(1))))
        )
        + "]",
        nodes=list(map(itemgetter(0), sorted(list(graph.uid_to_id.items()), key=itemgetter(1)))),
        node_map=[
            sorted([node.get_order() for node in nodes])
            for nodes in map(
                itemgetter(1),
                sorted(list(graph.uid_to_nodes.items()), key=lambda x: graph.uid_to_id[x[0]]),
            )
        ],
        selection_table=selection_table,
    )
    log.minor_success("HTML template", "rendered")
    output_file = diff_kit.save_diff_view(
        kwargs.get("output_file"), content, "sankey", lhs_profile, rhs_profile
    )
    log.minor_status("Output saved", log.path_style(output_file))


@click.command()
@click.option("-o", "--output-file", help="Sets the output file (default=automatically generated).")
@click.pass_context
def sankey_incr(ctx: click.Context, *_: Any, **kwargs: Any) -> None:
    """Creates sankey graphs representing the differences between two profiles"""
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    profile_list = ctx.parent.params["profile_list"]
    generate_sankey_difference(profile_list[0], profile_list[1], **kwargs)
