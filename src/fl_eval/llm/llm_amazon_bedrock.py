from __future__ import annotations

import os
from importlib import import_module
from typing import Any, Protocol, TypedDict, cast

from . import llm_configurations


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
        system: list[BedrockTextBlock],
    ) -> BedrockConverseResponse: ...

class AmazonBedrock_LLM(llm_configurations.LLM):
    def __init__(
        self,
        name: str,
        model: llm_configurations.ModelInfo,
        # The api_key is now primarily for mock mode, as boto3 pulls from env
        verbose: bool = False,
    ):
        super().__init__(name, model)
        self.model = model
        self.verbose = verbose
        self.chat_history = []
        self.system_prompt = "" # Assuming this is set elsewhere
        self.client: BedrockRuntimeClient | None

        api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        if not api_key:
            api_key = "NO_KEY"
        else:
            print("BEDROCK KEY PROVIDED")

        region = os.getenv("AWS_DEFAULT_REGION")
        if not region:
            print("NO BEDROCK API_DEFAULT_REGION provided, us-east-2 tends to be the better one")

        if api_key == "NO_KEY":
            print("NO BEDROCK API key provided — running in mock mode")
            self.client = None # Use None to signify mock mode
            return
            
        # Boto3 will automatically pick up the API key from the environment
        # variable AWS_BEARER_TOKEN_BEDROCK
        boto3_module = cast(Any, import_module("boto3"))
        self.client = cast(
            BedrockRuntimeClient,
            boto3_module.client(
                service_name="bedrock-runtime",
                region_name=region,
            ),
        )

    def reset_chat_history(self):
        self.chat_history = []

    def get_chat_history(self):
        return self.chat_history


    def _get_response(self, prompt: str) -> str:
        # ... (timing, chat_history update, _trim_context) ...
        if self.client is None:
            return "Mock Reply"

        # 1. Format messages for the standard Converse API
        # The Converse API requires content to be a list of dictionaries (e.g., [{'text': '...'}]
        bedrock_messages: list[dict[str, Any]] = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.chat_history
        ]

        prompt_message: dict[str, Any] = {"role": "user", "content": [{"text": prompt}]}
        
        bedrock_messages.append(prompt_message)
        # 2. Call the standardized Converse API
        response = self.client.converse(
            modelId=self.model.model_id,
            messages=bedrock_messages,
            system=[{"text": self.system_prompt}],
        )
     

        # 3. Extract the response
        reply = response['output']['message']['content'][0]['text']

        # ... (chat_history append, return reply)
        self.chat_history.append(prompt_message)
        self.chat_history.append({"role": "assistant", "content": [{"text": reply}]})
        return reply