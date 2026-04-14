from __future__ import annotations

from unittest.mock import Mock, patch

from fl_eval.llm.llm_amazon_bedrock import AmazonBedrock_LLM
from fl_eval.llm.llm_configurations import (
    LLM_COST_STUB_ALL_LINES_RANKED,
    LLM_YIELD_RESULT_WITHOUT_API,
    MODEL_REGISTRY,
)
from fl_eval.llm.llm_create import create_llm
from fl_eval.llm.llm_openrounter import OpenRouter_LLM


def test_without_api_interactive(monkeypatch):
    responses = iter(["first line", "second line", "#END#"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))

    llm = LLM_YIELD_RESULT_WITHOUT_API("interactive", MODEL_REGISTRY["without_api"])
    reply = llm.get_response("Prompt text")

    assert reply == "first line\nsecond line"
    assert llm.get_chat_history() == ["Prompt text", "first line\nsecond line"]


def test_stub_ranks_all_lines():
    llm = LLM_COST_STUB_ALL_LINES_RANKED("stub", MODEL_REGISTRY["cost_stub_all_lines_ranked"])

    reply = llm.get_response("line 1\nline 2\nline 3")

    assert reply == "[1, 2, 3]"
    assert llm.get_chat_history() == ["line 1\nline 2\nline 3", "[1, 2, 3]"]


def test_openrouter_mock_mode_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    llm = OpenRouter_LLM("openrouter", MODEL_REGISTRY["llama-3.1-8b-instruct-free"])
    reply = llm.get_response("Prompt text")

    assert reply == "Mock Reply"
    assert llm.get_chat_history() == []


def test_create_llm_supports_openrouter(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    llm = create_llm("openrouter-test", "qwen2.5-7b-instruct-free")

    assert isinstance(llm, OpenRouter_LLM)

