from fl_eval.util.counterexample_trace_utils import parse_counterexample_trace_report, rank_counterexample_nodes
from fl_eval.util.ranking_strategy import (
    CounterExampleRankingControls,
    NODE_SELECTION_POLICY_PURE_STATE,
)


def test_parse_counterexample_trace_report_keeps_non_initial_nodes_before_rank_dedup() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[
  {"line":7,"depth":0,"type":"State","source":"counterexample_state","content":"file.dfy(7,0): initial state:","parents":[]},
  {"line":8,"depth":2,"type":"Statement","source":"matched_statement","content":"var cubedArray := new int[a.Length];","parents":[]},
  {"line":8,"depth":0,"type":"State","source":"counterexample_state","content":"file.dfy(8,37):","parents":[]},
  {"line":9,"depth":0,"type":"State","source":"counterexample_state","content":"file.dfy(9,2): after some loop iterations:","parents":[]},
  {"line":16,"depth":2,"type":"Statement","source":"matched_statement","content":"return cubedArray;","parents":[]},
  {"line":16,"depth":0,"type":"State","source":"counterexample_state","content":"file.dfy(16,19):","parents":[]}
]}]}
JSON_OUTPUT_END
"""

    report = parse_counterexample_trace_report(stdout)

    assert report is not None
    assert len(report.traces) == 1
    assert len(report.traces[0]) == 5
    assert [node.line for node in report.traces[0]] == [8, 8, 9, 16, 16]
    assert report.traces[0][0].source == "matched_statement"
    assert report.traces[0][1].source == "counterexample_state"
    assert report.traces[0][2].source == "counterexample_state"
    assert report.payload["traces"][0]["nodes"][0]["source"] == "matched_statement"
    assert len(report.payload["traces"][0]["nodes"]) == 5


def test_rank_counterexample_nodes_uses_deduped_nodes() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[
  {"line":8,"depth":2,"type":"Statement","source":"matched_statement","content":"var cubedArray := new int[a.Length];","parents":[]},
  {"line":8,"depth":0,"type":"State","source":"counterexample_state","content":"file.dfy(8,37):","parents":[]},
  {"line":16,"depth":2,"type":"Statement","source":"matched_statement","content":"return cubedArray;","parents":[]}
]},{"trace_id":1,"nodes":[
  {"line":8,"depth":2,"type":"Statement","source":"matched_statement","content":"var cubedArray := new int[a.Length];","parents":[]}
]}]}
JSON_OUTPUT_END
"""

    report = parse_counterexample_trace_report(stdout)

    assert report is not None
    assert rank_counterexample_nodes(report.traces) == [8, 16]


def test_rank_counterexample_nodes_pure_state_policy_uses_only_counterexample_state() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[
  {"line":10,"depth":2,"type":"Statement","source":"matched_statement","content":"x := 1;","parents":[]},
  {"line":10,"depth":0,"type":"State","source":"counterexample_state","content":"file.dfy(10,1):","parents":[]},
  {"line":11,"depth":1,"type":"Statement","source":"matched_statement","content":"y := 2;","parents":[]}
]}]}
JSON_OUTPUT_END
"""
    report = parse_counterexample_trace_report(stdout)
    assert report is not None

    controls = CounterExampleRankingControls(
        node_selection_policy=NODE_SELECTION_POLICY_PURE_STATE,
    )
    assert rank_counterexample_nodes(report.traces, ranking_controls=controls) == [10]


def test_rank_counterexample_nodes_ablation_without_frequency_uses_depth_then_control() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[
  {"line":10,"depth":1,"type":"Statement","source":"matched_statement","content":"x := 1;","parents":[]},
  {"line":11,"depth":3,"type":"Statement","source":"matched_statement","content":"y := 2;","parents":[]}
]}]}
JSON_OUTPUT_END
"""
    report = parse_counterexample_trace_report(stdout)
    assert report is not None

    controls = CounterExampleRankingControls(use_frequency=False)
    assert rank_counterexample_nodes(report.traces, ranking_controls=controls) == [11, 10]


def test_rank_counterexample_nodes_ablation_without_depth_uses_frequency_then_control() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[
  {"line":10,"depth":1,"type":"Statement","source":"matched_statement","content":"x := 1;","parents":[]},
  {"line":11,"depth":5,"type":"Statement","source":"matched_statement","content":"y := 2;","parents":[]},
  {"line":10,"depth":2,"type":"Statement","source":"matched_statement","content":"x := 1;","parents":[]}
]}]}
JSON_OUTPUT_END
"""
    report = parse_counterexample_trace_report(stdout)
    assert report is not None

    controls = CounterExampleRankingControls(use_depth=False)
    assert rank_counterexample_nodes(report.traces, ranking_controls=controls) == [10, 11]


def test_rank_counterexample_nodes_ablation_without_control_uses_frequency_then_depth() -> None:
    stdout = """
JSON_OUTPUT_START
{"traces":[{"trace_id":0,"nodes":[
  {"line":10,"depth":4,"type":"Statement","source":"matched_statement","content":"x := 1;","parents":[]},
  {"line":11,"depth":2,"type":"WhileStmt","source":"matched_statement","content":"while ...","parents":[]}
]}]}
JSON_OUTPUT_END
"""
    report = parse_counterexample_trace_report(stdout)
    assert report is not None

    controls = CounterExampleRankingControls(use_control_statement=False)
    assert rank_counterexample_nodes(report.traces, ranking_controls=controls) == [10, 11]

