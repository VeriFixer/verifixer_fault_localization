from pathlib import Path
from typing import Any, cast

from fl_eval.tracing.trace_extractor import (
    extract_autofix_summary,
    extract_counterexample_base_summary,
    extract_counterexample_trace_summary,
    find_latest_autofix_csv,
)


def test_extract_counterexample_trace_summary_parses_marked_json() -> None:
    stdout = """
noise
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[{"line":10,"depth":1},{"line":15,"depth":1}]},{"trace_id":1,"nodes":[{"line":10,"depth":1},{"line":20,"depth":1}]}]}
JSON_OUTPUT_END
noise
"""

    summary = extract_counterexample_trace_summary(stdout)

    assert summary is not None
    assert summary.trace_count == 2
    assert summary.node_count == 4
    assert summary.unique_line_count == 3
    assert summary.top_lines[0] == (10, 2)


def test_extract_counterexample_trace_summary_handles_empty_traces() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[]}
JSON_OUTPUT_END
"""

    summary = extract_counterexample_trace_summary(stdout)

    assert summary is not None
    assert summary.trace_count == 0
    assert summary.node_count == 0
    assert summary.unique_line_count == 0
    assert summary.top_lines == []


def test_extract_counterexample_trace_summary_handles_traces_with_empty_nodes() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[]},{"trace_id":1,"nodes":[]}]} 
JSON_OUTPUT_END
"""

    summary = extract_counterexample_trace_summary(stdout)

    assert summary is not None
    assert summary.trace_count == 2
    assert summary.node_count == 0
    assert summary.unique_line_count == 0
    assert summary.top_lines == []


def test_extract_counterexample_trace_summary_ignores_malformed_nodes() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[{"line":7},{}]}, {"trace_id":1,"nodes":[{"line":"x"},42,null]}]}
JSON_OUTPUT_END
"""

    summary = extract_counterexample_trace_summary(stdout)

    assert summary is not None
    assert summary.trace_count == 2
    assert summary.node_count == 1
    assert summary.unique_line_count == 1
    assert summary.top_lines == [(7, 1)]


def test_extract_counterexample_trace_summary_returns_none_without_markers() -> None:
    stdout = '{"traces":[{"trace_id":0,"nodes":[{"line":10}]}]}'

    summary = extract_counterexample_trace_summary(stdout)

    assert summary is None


def test_extract_counterexample_trace_summary_skips_initial_state_nodes() -> None:
    """Test that initial state nodes are skipped and filtered from raw output."""
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[
  {"line":7,"content":"file.dfy(7,0): initial state:"},
  {"line":8,"content":"var x := 5;"},
  {"line":9,"content":"file.dfy(9,0): initial state:"},
  {"line":10,"content":"return x;"}
]}]}
JSON_OUTPUT_END
"""

    summary = extract_counterexample_trace_summary(stdout)

    assert summary is not None
    assert summary.trace_count == 1
    assert summary.node_count == 2  # Only 2 nodes counted (initial states skipped)
    assert summary.unique_line_count == 2  # Lines 8 and 10
    assert set(line for line, _ in summary.top_lines) == {8, 10}
    
    # Verify filtered raw output does not contain initial state nodes
    raw_payload = cast(dict[str, Any], summary.raw)
    filtered_traces = cast(list[dict[str, Any]], raw_payload.get("traces", []))
    assert len(filtered_traces) == 1
    filtered_nodes = cast(list[dict[str, Any]], filtered_traces[0].get("nodes", []))
    assert len(filtered_nodes) == 2  # Only 2 nodes in filtered output
    # Verify no "initial state:" in content
    for node in filtered_nodes:
        content = node.get("content", "")
        assert "initial state:" not in content



def test_extract_counterexample_trace_summary_deduplicates_lines_per_trace() -> None:
    """Test that each line is counted only once per trace."""
    stdout = """
JSON_OUTPUT_START
{"traces":[
  {"trace_id":0,"nodes":[
    {"line":10,"content":"statement 1"},
    {"line":10,"content":"statement 1"},
    {"line":10,"content":"statement 1"},
    {"line":15,"content":"statement 2"}
  ]},
  {"trace_id":1,"nodes":[
    {"line":10,"content":"statement 1"},
    {"line":20,"content":"statement 3"}
  ]}
]}
JSON_OUTPUT_END
"""

    summary = extract_counterexample_trace_summary(stdout)

    assert summary is not None
    assert summary.trace_count == 2
    assert summary.node_count == 4  # 4 representative nodes after per-trace dedupe
    assert summary.unique_line_count == 3  # 3 unique lines: 10, 15, 20
    # Line 10 appears in both traces but counted only once per trace = frequency 2
    assert summary.top_lines[0] == (10, 2)


def test_extract_counterexample_base_summary_parses_diagnostics() -> None:
    diagnostic_1 = '{"type":"diagnostic","value":{"defaultFormatMessage":"DafnyRef#sec-counterexamples\\nfoo.dfy(10, 3)\\nfoo.dfy(12, 2)"}}'
    diagnostic_2 = '{"type":"diagnostic","value":{"defaultFormatMessage":"DafnyRef#sec-counterexamples\\nfoo.dfy(12, 2)\\nRelated location foo.dfy(99, 1)"}}'
    stdout = diagnostic_1 + "\n" + diagnostic_2

    summary = extract_counterexample_base_summary(stdout)

    assert summary is not None
    assert summary.trace_count == 2
    # smallest line (10) is dropped as initial non-actionable line per strategy behavior.
    assert summary.top_lines[0][0] == 12
    assert summary.top_lines[0][1] == 2


def test_extract_autofix_summary_and_find_latest(tmp_path: Path) -> None:
    root = tmp_path / "autofix_runs"
    first_csv = root / "run1" / "mutant_a" / "lines-suspiciousness.csv"
    second_csv = root / "run2" / "mutant_a" / "lines-suspiciousness.csv"
    first_csv.parent.mkdir(parents=True, exist_ok=True)
    second_csv.parent.mkdir(parents=True, exist_ok=True)

    first_csv.write_text("10,0.30\n20,0.10\n", encoding="utf-8")
    second_csv.write_text("15,0.90\n18,0.20\n", encoding="utf-8")

    latest = find_latest_autofix_csv(root, "mutant_a")
    assert latest is not None

    summary = extract_autofix_summary(latest)
    assert summary is not None
    assert summary.line_count == 2
    assert summary.top_lines[0] == (15, 0.9)
    assert summary.max_score == 0.9
