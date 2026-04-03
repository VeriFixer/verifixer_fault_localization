from __future__ import annotations

from unittest.mock import Mock, patch

from fl_eval.llm.llm_amazon_bedrock import AmazonBedrock_LLM
from fl_eval.llm.llm_configurations import (
    LLM_COST_STUB_ALL_LINES_RANKED,
    LLM_YIELD_RESULT_WITHOUT_API,
    MODEL_REGISTRY,
)


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


def test_bedrock_converse_request(monkeypatch):
    fake_client = Mock()
    fake_client.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": "mock-bedrock-reply"}],
            }
        }
    }

    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")

    with patch("fl_eval.llm.llm_amazon_bedrock.import_module") as import_module_mock:
        boto_module = Mock()
        boto_module.client = Mock(return_value=fake_client)
        import_module_mock.return_value = boto_module
        llm = AmazonBedrock_LLM("bedrock", MODEL_REGISTRY["deepseek-r1"])
        llm.set_system_prompt("system prompt")
        reply = llm.get_response("What is happening?")

    assert reply == "mock-bedrock-reply"
    import_module_mock.assert_called_once_with("boto3")
    boto_module.client.assert_called_once_with(service_name="bedrock-runtime", region_name="us-west-2")
    fake_client.converse.assert_called_once()

    call_kwargs = fake_client.converse.call_args.kwargs
    assert call_kwargs["modelId"] == MODEL_REGISTRY["deepseek-r1"].model_id
    assert call_kwargs["system"] == [{"text": "system prompt"}]
    assert call_kwargs["messages"] == [
        {"role": "user", "content": [{"text": "What is happening?"}]}
    ]
    assert llm.get_chat_history() == [
        {"role": "user", "content": [{"text": "What is happening?"}]},
        {"role": "assistant", "content": [{"text": "mock-bedrock-reply"}]},
    ]