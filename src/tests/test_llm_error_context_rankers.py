from pathlib import Path

from fl_eval.execution.external_cmd import Status
from fl_eval.strategies.llm_err_msg import LLMErrMsgRanker
from fl_eval.strategies.llm_err_msg_cntm import LLMErrMsgCNTMRanker


def test_llm_err_msg_includes_raw_dafny_output_in_prompt(tmp_path: Path, monkeypatch):
    source = tmp_path / "sample.dfy"
    source.write_text("method Main() {\n  assert false;\n}\n", encoding="utf-8")

    def fake_run_external_cmd(_cmd: list[str], timeout: int = 0):
        return Status.OK, '{"type":"diagnostic","value":"x"}', ""

    monkeypatch.setattr(
        "fl_eval.strategies.llm_base_ranker.run_cmd.run_external_cmd",
        fake_run_external_cmd,
    )

    ranker = LLMErrMsgRanker(name="LLM_ERR_MSG")
    ranker.get_fault_localization(source)

    prompt, _response = ranker.llm.get_chat_history()
    assert "BEGIN_RAW_DAFNY_VERIFY_OUTPUT" in prompt
    assert 'STDOUT:\n{"type":"diagnostic","value":"x"}' in prompt


def test_llm_err_msg_cntm_includes_cntm_ranked_lines(tmp_path: Path, monkeypatch):
    source = tmp_path / "sample.dfy"
    source.write_text("method Main() {\n  assert false;\n}\n", encoding="utf-8")

    def fake_run_external_cmd(_cmd: list[str], timeout: int = 0):
        return Status.OK, '{"type":"diagnostic","value":"x"}', ""

    monkeypatch.setattr(
        "fl_eval.strategies.llm_base_ranker.run_cmd.run_external_cmd",
        fake_run_external_cmd,
    )

    monkeypatch.setattr(
        "fl_eval.strategies.counter_example_if_reassume.CounterExampleIfReassume.get_fault_localization",
        lambda self, file: [9, 3, 8],
    )

    ranker = LLMErrMsgCNTMRanker(name="LLM_ERR_MSG_CNTM")
    ranker.get_fault_localization(source)

    prompt, _response = ranker.llm.get_chat_history()
    assert "BEGIN_RAW_DAFNY_VERIFY_OUTPUT" in prompt
    assert "BEGIN_CNTM_RANKED_LINES\n[9, 3, 8]\nEND_CNTM_RANKED_LINES" in prompt


def test_llm_err_msg_cntm_handles_cntm_failure(tmp_path: Path, monkeypatch):
    source = tmp_path / "sample.dfy"
    source.write_text("method Main() {\n  assert false;\n}\n", encoding="utf-8")

    def fake_run_external_cmd(_cmd: list[str], timeout: int = 0):
        return Status.OK, '{"type":"diagnostic","value":"x"}', ""

    monkeypatch.setattr(
        "fl_eval.strategies.llm_base_ranker.run_cmd.run_external_cmd",
        fake_run_external_cmd,
    )

    def raise_cntm(_self, _file: Path):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "fl_eval.strategies.counter_example_if_reassume.CounterExampleIfReassume.get_fault_localization",
        raise_cntm,
    )

    ranker = LLMErrMsgCNTMRanker(name="LLM_ERR_MSG_CNTM")
    ranker.get_fault_localization(source)

    prompt, _response = ranker.llm.get_chat_history()
    assert "BEGIN_CNTM_RANKED_LINES\n[]\nEND_CNTM_RANKED_LINES" in prompt