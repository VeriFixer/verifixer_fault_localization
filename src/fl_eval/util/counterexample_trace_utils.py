from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, cast

from fl_eval.util.ranking_strategy import (
    CounterExampleNode,
    RANK_BY_FREQUENCY,
    RankingStrategy,
    SUPPORTED_RANKING_STRATEGIES,
)


@dataclass(frozen=True)
class CounterExampleTraceReport:
    payload: dict[str, Any]
    nodes: list[CounterExampleNode]


@dataclass
class LineFrequencyDepth:
    frequency: int = 0
    depths: list[int] = field(default_factory=lambda: cast(list[int], []))
    types: list[str] = field(default_factory=lambda: cast(list[str], []))


_JSON_MARKERS_PATTERN = re.compile(r"JSON_OUTPUT_START\s*(.*?)\s*JSON_OUTPUT_END", re.S)


def _is_initial_state_node(node: dict[str, Any]) -> bool:
    content = node.get("content")
    return isinstance(content, str) and "initial state:" in content


def _parse_node(node: dict[str, Any], trace_id: int) -> CounterExampleNode | None:
    line = node.get("line")
    if not isinstance(line, int):
        return None

    depth = node.get("depth", 0)
    parents_payload = node.get("parents", [])
    parents: list[tuple[str, int]] = []
    if isinstance(parents_payload, list):
        for parent in cast(list[Any], parents_payload):
            if isinstance(parent, dict):
                parent_dict = cast(dict[str, Any], parent)
                parent_type = str(parent_dict.get("parent_node_type", ""))
                parent_line = parent_dict.get("parent_node_line")
                if isinstance(parent_line, int):
                    parents.append((parent_type, parent_line))

    return CounterExampleNode(
        line=line,
        depth=int(depth) if isinstance(depth, int) else 0,
        type=str(node.get("type", "")),
        source=str(node.get("source", "")),
        content=str(node.get("content", "")),
        trace_id=trace_id,
        parents=parents,
    )


def parse_counterexample_trace_report(stdout: str) -> CounterExampleTraceReport | None:
    match = _JSON_MARKERS_PATTERN.search(stdout)
    if not match:
        return None

    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        return None

    payload_dict = cast(dict[str, Any], payload)
    traces = payload_dict.get("traces")
    if not isinstance(traces, list):
        return None

    filtered_traces: list[dict[str, Any]] = []
    nodes: list[CounterExampleNode] = []

    for trace in cast(list[Any], traces):
        if not isinstance(trace, dict):
            continue

        trace_dict = cast(dict[str, Any], trace)
        trace_nodes = trace_dict.get("nodes", [])
        if not isinstance(trace_nodes, list):
            continue

        trace_id_raw = trace_dict.get("trace_id", 0)
        trace_id = int(trace_id_raw) if isinstance(trace_id_raw, int) else 0
        representatives: dict[int, tuple[CounterExampleNode, dict[str, Any]]] = {}

        for node in cast(list[Any], trace_nodes):
            if not isinstance(node, dict):
                continue

            node_dict = cast(dict[str, Any], node)
            if _is_initial_state_node(node_dict):
                continue

            parsed_node = _parse_node(node_dict, trace_id)
            if parsed_node is None:
                continue

            line = parsed_node.line
            current = representatives.get(line)
            if current is None or (current[0].source == "counterexample_state" and parsed_node.source != "counterexample_state"):
                representatives[line] = (parsed_node, node_dict)

        filtered_trace = dict(trace_dict)
        filtered_trace["nodes"] = [node_dict for _, node_dict in representatives.values()]
        filtered_traces.append(filtered_trace)
        nodes.extend(node for node, _ in representatives.values())

    filtered_payload = dict(payload_dict)
    filtered_payload["traces"] = filtered_traces

    return CounterExampleTraceReport(payload=filtered_payload, nodes=nodes)


def rank_counterexample_nodes(
    nodes: list[CounterExampleNode],
    ranking_strategy: RankingStrategy = RANK_BY_FREQUENCY,
) -> list[int]:
    if ranking_strategy not in SUPPORTED_RANKING_STRATEGIES:
        raise ValueError(
            f"Unknown ranking strategy '{ranking_strategy}'. "
            f"Supported: {[s.name for s in SUPPORTED_RANKING_STRATEGIES]}"
        )

    line_freq_depth_map: dict[int, LineFrequencyDepth] = {}
    first_seen_order: dict[int, int] = {}

    for idx, node in enumerate(nodes):
        if node.line not in first_seen_order:
            first_seen_order[node.line] = idx

        if node.line in line_freq_depth_map:
            line_freq_depth_map[node.line].frequency += 1
            line_freq_depth_map[node.line].depths.append(node.depth)
            line_freq_depth_map[node.line].types.append(node.type)
        else:
            line_freq_depth_map[node.line] = LineFrequencyDepth(
                frequency=1,
                depths=[node.depth],
                types=[node.type],
            )

    def has_control_statement_type(types: list[str]) -> bool:
        for node_type in types:
            if node_type in ("IfStmt", "WhileStmt"):
                return True
        return False

    return sorted(
        line_freq_depth_map.keys(),
        key=lambda line: (
            -line_freq_depth_map[line].frequency,
            -max(line_freq_depth_map[line].depths),
            -int(has_control_statement_type(line_freq_depth_map[line].types)),
            first_seen_order[line],
        ),
    )
