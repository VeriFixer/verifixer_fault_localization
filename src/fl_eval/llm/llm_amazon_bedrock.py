from __future__ import annotations

import os
import time
from importlib import import_module
from typing import Any, Protocol, TypedDict, cast

from botocore.config import Config

from logging_config import get_logger

from .llm_configurations import LLM, ModelInfo

logger = get_logger(__name__)


class BedrockTextBlock(TypedDict):
    text: str


class BedrockResponseMessage(TypedDict):
    content: list[BedrockTextBlock]


class BedrockResponseOutput(TypedDict):
    message: BedrockResponseMessage


class BedrockConverseResponse(TypedDict):
    output: BedrockResponseOutput


class BedrockRuntimeClient(Protocol):
    def converse(
        self,
        *,
        modelId: str,
        messages: list[dict[str, Any]],
        system: list[BedrockTextBlock] | None = None,
    ) -> BedrockConverseResponse: ...


class AmazonBedrock_LLM(LLM):
    def __init__(
        self,
        name: str,
        model: ModelInfo,
        verbose: bool = False,
    ):
        super().__init__(name, model)
        self.model = model
        self.verbose = verbose
        self.chat_history: list[dict[str, Any]] = []
        self.system_prompt = "You are a specialist in code fault localization"
        self.quota_exhausted = False
        self.request_delay_seconds = 0.6
        self.response_delay_seconds = 0.75
        self.throttle_delay_seconds = 3.0
        self.client: BedrockRuntimeClient | None

        api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        if not api_key:
            logger.warning("NO BEDROCK API key provided - running in mock mode")
            self.client = None
            return

        logger.info("BEDROCK KEY PROVIDED")

        region = os.getenv("AWS_DEFAULT_REGION")
        if not region:
            logger.warning(
                "NO BEDROCK AWS_DEFAULT_REGION provided; us-east-2 tends to be the better one"
            )

        boto3_module = cast(Any, import_module("boto3"))
        # Explicitly keep Bedrock requests single-attempt (no SDK retries).
        config = Config(
            retries={"total_max_attempts": 1, "mode": "standard"}
        )
        self.client = cast(
            BedrockRuntimeClient,
            boto3_module.client(
                service_name="bedrock-runtime",
                region_name=region,
                config=config,
            ),
        )

    def _extract_error_code_message(self, exc: Exception) -> tuple[str, str]:
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return "", str(exc)

        err = response.get("Error")
        if not isinstance(err, dict):
            return "", str(exc)

        code = str(err.get("Code", ""))
        message = str(err.get("Message", ""))
        return code, message

    def _to_bedrock_content(self, msg: dict[str, Any]) -> list[BedrockTextBlock]:
        content = msg.get("content")

        if isinstance(content, list):
            out: list[BedrockTextBlock] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        out.append({"text": text_value})
            return out

        if isinstance(content, str):
            return [{"text": content}]

        return []

    def _get_response(self, prompt: str) -> str:
        if self.client is None:
            return "Mock Reply"

        if self.quota_exhausted:
            # Keep downstream parsing stable and avoid repeated failing API calls.
            return "[]"

        bedrock_messages: list[dict[str, Any]] = []
        for msg in self.chat_history:
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            content_blocks = self._to_bedrock_content(msg)
            if not content_blocks:
                continue
            bedrock_messages.append({"role": role, "content": content_blocks})

        prompt_message: dict[str, Any] = {"role": "user", "content": [{"text": prompt}]}
        bedrock_messages.append(prompt_message)

        request_kwargs: dict[str, Any] = {
            "modelId": self.model.model_id,
            "messages": bedrock_messages,
        }

        system_prompt = self.system_prompt.strip()
        if system_prompt:
            request_kwargs["system"] = [{"text": system_prompt}]

        if self.request_delay_seconds > 0:
            time.sleep(self.request_delay_seconds)

        try:
            response = self.client.converse(**request_kwargs)
        except Exception as e:
            code, message = self._extract_error_code_message(e)
            if code == "ThrottlingException":
                if "Too many tokens per day" in message:
                    self.quota_exhausted = True
                    logger.warning(
                        "Bedrock daily token quota exhausted for model '%s'. "
                        "Disabling further Bedrock calls for this run. Error: %s",
                        self.model.model_id,
                        e,
                    )
                else:
                    logger.warning(
                        "Bedrock throttling for model '%s'. Returning empty prediction for this call. Error: %s",
                        self.model.model_id,
                        e,
                    )
                if self.throttle_delay_seconds > 0:
                    time.sleep(self.throttle_delay_seconds)
                return "[]"

            if code or message:
                raise RuntimeError(f"Bedrock Converse request failed: {code}: {message}") from e
            raise

        reply = response["output"]["message"]["content"][0]["text"]
        self.chat_history.append({"role": "user", "content": prompt})
        self.chat_history.append({"role": "assistant", "content": reply})
        if self.response_delay_seconds > 0:
            time.sleep(self.response_delay_seconds)

        return reply
