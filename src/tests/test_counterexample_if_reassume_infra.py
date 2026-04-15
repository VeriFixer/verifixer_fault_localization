import json
import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE = REPO_ROOT / "build_output" / "CounterExampleIfReassume" / "CounterExampleIfReassume"


def _run_counterexample_if_reassume(mutant_rel_path: str, max_time: int = 10, timeout: int = 90) -> tuple[int, str, str]:
    if not EXECUTABLE.is_file():
        pytest.skip(f"CounterExampleIfReassume executable not found at {EXECUTABLE}")

    cmd = [
        str(EXECUTABLE),
        str(REPO_ROOT / mutant_rel_path),
        "--max-time",
        str(max_time),
        "--max-ram",
        "24",
    ]

    completed = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _extract_trace_and_node_counts(stdout: str) -> tuple[int, int]:
    match = re.search(r"JSON_OUTPUT_START\s*(.*?)\s*JSON_OUTPUT_END", stdout, re.S)
    assert match is not None, "Missing JSON_OUTPUT_START/JSON_OUTPUT_END markers in C# output"

    payload = json.loads(match.group(1))
    traces = payload.get("traces")
    assert isinstance(traces, list), "Payload must contain a traces array"

    node_count = 0
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        nodes = trace.get("nodes")
        if isinstance(nodes, list):
            node_count += len(nodes)

    return len(traces), node_count


@pytest.mark.parametrize(
    ("mutant_rel_path", "expected_min_traces", "expected_min_nodes"),
    [
        # User-provided basic example baseline.
        ("datasets/pos_test/killed/example_to_test_reassume__MUTANT.dfy", 4, 20),
        # Previously failing baselines for debugging.
        ("datasets/pos_test/killed/Dafny-Practice_tmp_tmphnmt4ovh_BST__3880-3880_AOI.dfy", 1, 10),
        ("datasets/pos_test/killed/abs__171-182_SDL.dfy", 1, 2),
        ("datasets/pos_test/killed/dafny-duck_tmp_tmplawbgxjo_p4__526_AOR_Sub.dfy", 2, 10),
    ],
)
def test_counterexample_if_reassume_csharp_output_baselines(
    mutant_rel_path: str,
    expected_min_traces: int,
    expected_min_nodes: int,
) -> None:
    return_code, stdout, _stderr = _run_counterexample_if_reassume(mutant_rel_path)

    assert return_code == 0
    traces, nodes = _extract_trace_and_node_counts(stdout)
    assert traces >= expected_min_traces
    assert nodes >= expected_min_nodes
