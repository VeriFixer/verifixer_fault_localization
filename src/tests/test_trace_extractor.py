from pathlib import Path

from fl_eval.util.trace_extractor import (
    extract_autofix_summary,
    extract_counterexample_base_summary,
    extract_counterexample_trace_summary,
    find_latest_autofix_csv,
)


def test_extract_counterexample_trace_summary_parses_marked_json() -> None:
    stdout = """
noise
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[{"line":10,"depth":1},{"line":10,"depth":2},{"line":15,"depth":1}]},{"trace_id":1,"nodes":[{"line":20,"depth":1}]}]}
JSON_OUTPUT_END
noise
"""

    summary = extract_counterexample_trace_summary(stdout)

    assert summary is not None
    assert summary.trace_count == 2
    assert summary.node_count == 4
    assert summary.unique_line_count == 3
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
