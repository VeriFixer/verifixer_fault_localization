from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, cast

from fl_eval.util.ranking_strategy import (
    DEFAULT_COUNTEREXAMPLE_RANKING_CONTROLS,
    CounterExampleRankingControls,
    CounterExampleNode,
    NODE_SELECTION_POLICY_PURE_STATE,
    NODE_SELECTION_POLICY_REGULAR,
    RANK_BY_FREQUENCY,
    RankingStrategy,
    RANK_BY_ORDER,
    SUPPORTED_NODE_SELECTION_POLICIES,
)


@dataclass(frozen=True)
class CounterExampleTraceReport:
    payload: dict[str, Any]
    traces: list[list[CounterExampleNode]]


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
    parsed_traces: list[list[CounterExampleNode]] = []

    for trace in cast(list[Any], traces):
        if not isinstance(trace, dict):
            continue

        trace_dict = cast(dict[str, Any], trace)
        trace_nodes = trace_dict.get("nodes", [])
        if not isinstance(trace_nodes, list):
            continue

        trace_id_raw = trace_dict.get("trace_id", 0)
        trace_id = int(trace_id_raw) if isinstance(trace_id_raw, int) else 0
        parsed_trace_nodes: list[CounterExampleNode] = []
        filtered_nodes_for_payload: list[dict[str, Any]] = []

        for node in cast(list[Any], trace_nodes):
            if not isinstance(node, dict):
                continue

            node_dict = cast(dict[str, Any], node)
            if _is_initial_state_node(node_dict):
                continue

            parsed_node = _parse_node(node_dict, trace_id)
            if parsed_node is None:
                continue

            parsed_trace_nodes.append(parsed_node)
            filtered_nodes_for_payload.append(node_dict)

        filtered_trace = dict(trace_dict)
        filtered_trace["nodes"] = filtered_nodes_for_payload
        filtered_traces.append(filtered_trace)
        parsed_traces.append(parsed_trace_nodes)

    filtered_payload = dict(payload_dict)
    filtered_payload["traces"] = filtered_traces

    return CounterExampleTraceReport(payload=filtered_payload, traces=parsed_traces)


def rank_counterexample_nodes(
    traces: list[list[CounterExampleNode]],
    ranking_strategy: RankingStrategy = RANK_BY_FREQUENCY,
    ranking_controls: CounterExampleRankingControls = DEFAULT_COUNTEREXAMPLE_RANKING_CONTROLS,
) -> list[int]:
    if ranking_controls.node_selection_policy not in SUPPORTED_NODE_SELECTION_POLICIES:
        raise ValueError(
            f"Unknown node selection policy '{ranking_controls.node_selection_policy}'. "
            f"Supported: {[s.name for s in SUPPORTED_NODE_SELECTION_POLICIES]}"
        )

    selected_nodes = _select_nodes_for_ranking(traces, ranking_controls)
    if not selected_nodes:
        return []

    line_freq_depth_map: dict[int, LineFrequencyDepth] = {}
    first_seen_order: dict[int, int] = {}

    for idx, node in enumerate(selected_nodes):
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

    def ranking_key(line: int) -> tuple[int, ...]:
        line_data = line_freq_depth_map[line]

        if ranking_strategy == RANK_BY_ORDER:
            return (first_seen_order[line],)

        criteria: list[int] = []
        if ranking_controls.use_frequency:
            criteria.append(-line_data.frequency)
        if ranking_controls.use_depth:
            criteria.append(-max(line_data.depths))
        if ranking_controls.use_control_statement:
            criteria.append(-int(has_control_statement_type(line_data.types)))

        criteria.append(first_seen_order[line])
        return tuple(criteria)

    return sorted(
        line_freq_depth_map.keys(),
        key=ranking_key,
    )


def _select_nodes_for_ranking(
    traces: list[list[CounterExampleNode]],
    ranking_controls: CounterExampleRankingControls,
) -> list[CounterExampleNode]:
    selected_nodes: list[CounterExampleNode] = []
    for trace_nodes in traces:
        grouped_by_line: dict[int, list[CounterExampleNode]] = {}
        line_order: list[int] = []

        for node in trace_nodes:
            if node.line not in grouped_by_line:
                grouped_by_line[node.line] = []
                line_order.append(node.line)
            grouped_by_line[node.line].append(node)

        for line in line_order:
            representative = _pick_representative_node(
                grouped_by_line[line],
                ranking_controls,
            )
            if representative is not None:
                selected_nodes.append(representative)

    return selected_nodes


def _pick_representative_node(
    candidates: list[CounterExampleNode],
    ranking_controls: CounterExampleRankingControls,
) -> CounterExampleNode | None:
    if ranking_controls.node_selection_policy == NODE_SELECTION_POLICY_PURE_STATE:
        for candidate in candidates:
            if candidate.source == "counterexample_state":
                return candidate
        return None

    if ranking_controls.node_selection_policy == NODE_SELECTION_POLICY_REGULAR:
        for candidate in candidates:
            if candidate.source != "counterexample_state":
                return candidate
        return candidates[0] if candidates else None

    return candidates[0] if candidates else None
