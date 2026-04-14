from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class CounterExampleTraceSummary:
    source: str
    trace_count: int
    node_count: int
    unique_line_count: int
    top_lines: list[tuple[int, int]]
    raw : str


@dataclass(frozen=True)
class AutoFixSummary:
    csv_path: Path
    line_count: int
    top_lines: list[tuple[int, float]]
    min_score: float
    max_score: float
    avg_score: float


_LINE_COLUMN_PATTERN = re.compile(r"dfy\((\d+),\s*\d+\)")


def extract_counterexample_trace_summary(stdout: str, top_n: int = 10) -> CounterExampleTraceSummary | None:
    """Extract a line-frequency summary from CounterExampleIf/CounterExampleIfReassume JSON output."""
    match = re.search(r"JSON_OUTPUT_START\s*(.*?)\s*JSON_OUTPUT_END", stdout, re.S)
    if not match:
        return None

    payload = json.loads(match.group(1))
    raw = payload
    if not isinstance(payload, dict):
        return None
    payload_dict = cast(dict[str, Any], payload)
    traces = payload_dict.get("traces")
    if not isinstance(traces, list):
        return None

    all_lines: list[int] = []
    trace_count = 0
    node_count = 0
    for trace in cast(list[Any], traces):
        if not isinstance(trace, dict):
            continue
        trace_dict = cast(dict[str, Any], trace)
        trace_nodes = trace_dict.get("nodes", [])
        if not isinstance(trace_nodes, list):
            continue
        trace_count += 1
        for node in cast(list[Any], trace_nodes):
            if not isinstance(node, dict):
                continue
            node_dict = cast(dict[str, Any], node)
            line = node_dict.get("line")
            if isinstance(line, int):
                all_lines.append(line)
                node_count += 1

    line_counts = Counter(all_lines)
    top_lines = [(line, freq) for line, freq in line_counts.most_common(top_n)]

    return CounterExampleTraceSummary(
        source="counterexample-json",
        trace_count=trace_count,
        node_count=node_count,
        unique_line_count=len(line_counts),
        top_lines=top_lines,
        raw=raw
    )


def extract_counterexample_base_summary(stdout: str, top_n: int = 10) -> CounterExampleTraceSummary | None:
    """Extract a line-frequency summary from CounterExampleBase JSON diagnostics output."""
    placeholder = "___ESCAPED_NEWLINE_PLACEHOLDER___"
    result_changed_stdout = stdout.replace("\\n", placeholder)
    lines = [r for r in result_changed_stdout.split("\n") if r]
    results_json_list = [r.replace(placeholder, "\\n") for r in lines]
    raw = stdout
    diagnostics: list[dict[str, Any]] = []
    for result in results_json_list:
        try:
            result_json = json.loads(result)
        except json.JSONDecodeError:
            continue
        if isinstance(result_json, dict):
            result_dict = cast(dict[str, Any], result_json)
            if result_dict.get("type") == "diagnostic":
                diagnostics.append(result_dict)

    if not diagnostics:
        return None

    all_lines: list[int] = []
    trace_count = 0
    for diagnostic in diagnostics:
        value = diagnostic.get("value")
        if not isinstance(value, dict):
            continue
        value_dict = cast(dict[str, Any], value)
        counter_message = value_dict.get("defaultFormatMessage")
        if not isinstance(counter_message, str):
            continue

        if "DafnyRef#sec-counterexamples" not in counter_message:
            continue

        trace_count += 1
        for raw_line in counter_message.split("\n"):
            if "Related location" in raw_line:
                continue
            matches = _LINE_COLUMN_PATTERN.findall(raw_line)
            for line_str in matches:
                all_lines.append(int(line_str))

    line_counts = Counter(all_lines)
    if line_counts and min(line_counts.keys()) in line_counts:
        # CounterExampleBase often includes an initial line that is not actionable.
        smallest_line = min(line_counts.keys())
        line_counts.pop(smallest_line, None)

    top_lines = [(line, freq) for line, freq in line_counts.most_common(top_n)]

    return CounterExampleTraceSummary(
        source="counterexample-base",
        trace_count=trace_count,
        node_count=sum(line_counts.values()),
        unique_line_count=len(line_counts),
        top_lines=top_lines,
        raw=stdout
    )


def find_latest_autofix_csv(output_root: Path, mutant_stem: str) -> Path | None:
    """Find the latest AutoFix lines-suspiciousness.csv for a given mutant stem."""
    if not output_root.is_dir():
        return None

    candidates = list(output_root.glob(f"*/{mutant_stem}/lines-suspiciousness.csv"))
    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)


def extract_autofix_summary(csv_path: Path, top_n: int = 10) -> AutoFixSummary | None:
    """Extract top suspicious lines and score statistics from AutoFix CSV output."""
    if not csv_path.is_file():
        return None

    rows: list[tuple[int, float]] = []
    with csv_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                line_no = int(parts[0].strip())
                score = float(parts[1].strip())
            except ValueError:
                continue
            rows.append((line_no, score))

    if not rows:
        return None

    scores = [score for _, score in rows]
    top_lines = sorted(rows, key=lambda x: x[1], reverse=True)[:top_n]

    return AutoFixSummary(
        csv_path=csv_path,
        line_count=len(rows),
        top_lines=top_lines,
        min_score=min(scores),
        max_score=max(scores),
        avg_score=sum(scores) / len(scores),
    )