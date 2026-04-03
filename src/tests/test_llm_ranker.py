from pathlib import Path

from fl_eval.strategies.llm_ranker import LLMRanker


def test_llm_ranker_with_stub_returns_sequential_ranking(tmp_path: Path):
    source = tmp_path / "sample.dfy"
    source.write_text(
        "method Main() {\n"
        "  var x := 1;\n"
        "  assert x == 1;\n"
        "}\n",
        encoding="utf-8",
    )

    ranker = LLMRanker(name="llm_stub_all_lines_ranked")
    predictions = ranker.get_fault_localization(source)

    assert predictions == [1, 2, 3, 4]


def test_llm_ranker_builds_numbered_prompt(tmp_path: Path):
    source = tmp_path / "sample.dfy"
    source.write_text("line one\nline two\n", encoding="utf-8")

    ranker = LLMRanker(name="llm_stub_all_lines_ranked")
    ranker.get_fault_localization(source)

    prompt, response = ranker.llm.get_chat_history()

    assert "BEGIN_FILE" in prompt
    assert "1: line one" in prompt
    assert "2: line two" in prompt
    assert response == "[1, 2]"