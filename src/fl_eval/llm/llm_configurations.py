import json

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ProviderInfo:
    name: str


PROVIDER_BEDROCK = ProviderInfo(name="bedrock")
PROVIDER_OPENROUTER = ProviderInfo(name="openrouter")
PROVIDER_DEBUG = ProviderInfo(name="debug")


@dataclass(frozen=True)
class ModelInfo:
    provider: ProviderInfo
    model_id: str          # provider-specific model id
    max_context: int
    cost_1M_in : float
    cost_1M_out : float


MODEL_REGISTRY: dict[str, ModelInfo] = {

    # --- Open-source on Bedrock (On-Demand Pricing) ---
    #https://aws.amazon.com/bedrock/pricing/
    "deepseek-r1": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="us.deepseek.r1-v1:0",
        max_context=64_000, # DeepSeek API documentation suggests 64K context
        cost_1M_in=1.35, # $0.00135 per 1K tokens
        cost_1M_out=5.40  # $0.0054 per 1K tokens
    ),
    "qwen3-coder-480b": ModelInfo(
        #provider=PROVIDER_BEDROCK,
        #model_id="qwen.qwen3-coder-480b-a35b-v1:0",
        provider=PROVIDER_OPENROUTER,
        model_id="meta-llama/llama-3.1-8b-instruct:free",
        max_context=262_000, # Context window of 262K tokens
        cost_1M_in=0.45,     # Low-end quote from Source 3.2, rounded from $0.22/M to be conservative
        cost_1M_out=1.8
    ),
    # Source: OpenRouter API comparison, often reflecting Bedrock rates: https://openrouter.ai/compare/amazon/nova-premier-v1/qwen/qwen3-coder (Source 3.2, lower quote)
    "qwen3-coder-30b": ModelInfo(
        provider=PROVIDER_BEDROCK,
        model_id="qwen.qwen3-coder-30b-a3b-v1:0",
        max_context=128_000,
        cost_1M_in=0.15,     # Highly competitive pricing, derived from 1K token rates (Source 3.2, lower quote)
        cost_1M_out=0.60
    ),

    # --- OpenRouter open-source models ---
    # Source: OpenRouter model catalog / free open-source models.
    "llama-3.1-8b-instruct-free": ModelInfo(
        provider=PROVIDER_OPENROUTER,
        model_id="meta-llama/llama-3.1-8b-instruct:free",
        max_context=128_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0,
    ),
    "qwen2.5-7b-instruct-free": ModelInfo(
        provider=PROVIDER_OPENROUTER,
        model_id="qwen/qwen-2.5-7b-instruct:free",
        max_context=128_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0,
    ),

    "cost_stub_all_lines_ranked": ModelInfo(
        provider=PROVIDER_DEBUG,
        model_id="all_lines_ranked",
        max_context=128_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0
    ),

    # Debug Interactive
    "without_api": ModelInfo(
        provider=PROVIDER_DEBUG,
        model_id="without_api",
        max_context=128_000,
        cost_1M_in=0.0,
        cost_1M_out=0.0
    ),
}

class LLM:
    def __init__(self, name: str, model : ModelInfo):
        self.name = name 
        self.model = model 

        self.system_prompt = ""

        # Handled directly by This parent Class
        self.total_chars_prompted : int = 0
        self.total_chars_response : int = 0
        self.prompt_number : int = 0


        # Variable to be handled by the implementations
        self.reasoning_tokens_output : int = 0

        self.chat_history: list[Any] = []
    def __str__(self):
        return f"LLM({self.name})"
    
    def get_name(self):
        return self.name
    
    def set_system_prompt(self, message : str):
        self.system_prompt = message

    def reset_chat_history(self):
        self.chat_history = []

    def get_chat_history(self):
        return self.chat_history

    def _get_response(self, prompt: str) -> str:
        raise NotImplementedError("Subclasses must implement the _generate_response method for API interaction.")
 
    def get_response(self, prompt: str) -> str:
        """
        Public method that handles logging and calls the subclass's implementation.
        """
        prompt_len = len(prompt)
        self.total_chars_prompted += prompt_len
        self.prompt_number += 1
        
        response = self._get_response(prompt)
        
        response_len = len(response)
        self.total_chars_response += response_len
        
        return response
    def get_my_cost_statisitcs(self):
        return self.get_cost_statistics(self.model)

    # Backward-compatible alias with corrected spelling.
    def get_my_cost_statistics(self):
        return self.get_my_cost_statisitcs()

    def get_cost_statistics(self, model : ModelInfo):
        mi = model

        how_many_chars_per_token = 3
        num_tokens_input = self.total_chars_prompted / how_many_chars_per_token
        num_tokens_output = self.total_chars_response / how_many_chars_per_token
        
        cost_input = (num_tokens_input / 1_000_000) * mi.cost_1M_in
        cost_output = (num_tokens_output / 1_000_000) * mi.cost_1M_out

        cost_reasoning = (self.reasoning_tokens_output / 1_000_000) * mi.cost_1M_out
     
        total_cost = cost_input + cost_output + cost_reasoning

        print(f"Expected Prices Model name: {self.name} Model id: {model.model_id}")
        print(f"{'Statistic':<40}{'Value':<20}")
        print("=" * 40)
        print(f"{'Total Prompts ':<40}{self.prompt_number:<20}")
        print(f"{'Total Chars Prompted ':<40}{self.total_chars_prompted:<20}")
        print(f"{'Total Chars Response ':<40}{self.total_chars_response:<20}")
        print(f"{'Total Tokens Input ':<40}{num_tokens_input:<20.2f}")
        print(f"{'Total Tokens Output ':<40}{num_tokens_output:<20.2f}")
        print(f"{'Total Tokens Output Reason':<40}{self.reasoning_tokens_output:<20.2f}")
        print(f"{'Cost Input ($) ':<40}{cost_input:<20.6f}")
        print(f"{'Cost Output ($) ':<40}{cost_output:<20.6f}")
        print(f"{'Cost Output Reason($) ':<40}{cost_reasoning:<20.6f}")
        print(f"{'Total Cost ($) ':<40}{total_cost:<20.6f}")
        print("=" * 40)

    def reset_all_measurement(self):
        self.total_chars_prompted = 0
        self.total_chars_response = 0
        self.prompt_number = 0


# Stub for LLM to account number of bytes etc

# Rule of tumb for LLM 1 token ~= 3 chars in English
class LLM_EMPTY_RESPONSE_STUB(LLM):  # 'extends' should be 'LLM_STUB(LLM)'
    def _get_response(self, prompt : str) -> str:  # Fix indentation
        return "" # Return exacly unchanged prompt is a good upper bound in total size
    
class LLM_COST_STUB_ALL_LINES_RANKED(LLM):  # 'extends' should be 'LLM_STUB(LLM)'
    def _get_response(self, prompt:str):  # Fix indentation
        self.chat_history.append(prompt) # orinal prompt

        file_section = prompt
        if "BEGIN_FILE" in prompt and "END_FILE" in prompt:
            file_section = prompt.split("BEGIN_FILE", 1)[1].split("END_FILE", 1)[0]

        source_lines = [line for line in file_section.splitlines() if line.strip()]
        response = json.dumps(list(range(1, len(source_lines) + 1)))
        self.chat_history.append(response)
        return response #

class LLM_COST_STUB_RESPONSE_IS_PROMPT(LLM):  # 'extends' should be 'LLM_STUB(LLM)'
    def _get_response(self, prompt:str):  # Fix indentation
        self.chat_history.append(prompt) # orinal prompt
        if("JSON array of line numbers ONLY" in prompt): #fix position prompt
          response = json.dumps([10,11])
        else:
          response = json.dumps([[f"assert 123452==123452 && {i} == {i};" for i in range(10)]*2])
        self.chat_history.append(response)
        return response # Return exacly unchanged prompt is a good upper bound in total size
    
# This allows to test setup through CHAT
class LLM_YIELD_RESULT_WITHOUT_API(LLM):  # 'extends' should be 'LLM_STUB(LLM)'
    def _get_response(self, prompt:str): 
        self.chat_history.append(prompt)
        print("The prompt is Prompt\n")
        print(f"System Prompt: {self.system_prompt}\n") 
        print(f"Main Prompt: {prompt}\n") 

        response = input("Enter your response (write #END# to end):\n")  

        # Read multiple lines until an empty line is entered
        lines = [response]
        while True:
            line = input()
            if line == "#END#":
                break
            lines.append(line)

        response = "\n".join(lines)  # Combine lines into a single response
        self.chat_history.append(response)
        return response  # Return exactly what the user provided
