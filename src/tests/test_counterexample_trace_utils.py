from fl_eval.util.counterexample_trace_utils import parse_counterexample_trace_report, rank_counterexample_nodes


def test_parse_counterexample_trace_report_prefers_non_state_nodes_for_same_line() -> None:
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
    assert len(report.nodes) == 3
    assert [node.line for node in report.nodes] == [8, 9, 16]
    assert report.nodes[0].source == "matched_statement"
    assert report.nodes[1].source == "counterexample_state"
    assert report.nodes[2].source == "matched_statement"
    assert report.payload["traces"][0]["nodes"][0]["source"] == "matched_statement"
    assert len(report.payload["traces"][0]["nodes"]) == 3


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
    assert rank_counterexample_nodes(report.nodes) == [8, 16]

