from .llm_configurations import (
    LLM,
    LLM_COST_STUB_ALL_LINES_RANKED,
    LLM_COST_STUB_RESPONSE_IS_PROMPT,
    LLM_YIELD_RESULT_WITHOUT_API,
    MODEL_REGISTRY,
)
from .llm_amazon_bedrock import AmazonBedrock_LLM

def create_llm(name: str, model: str, *, verbose: bool = False) -> LLM:
    if model not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model}")

    info = MODEL_REGISTRY[model]

    if info.provider == "bedrock":
        return AmazonBedrock_LLM(name, info, verbose=verbose)
    
    if info.provider == "debug":
        if model == "cost_stub_all_lines_ranked":
            return LLM_COST_STUB_ALL_LINES_RANKED(name, info)
        elif model == "without_api":
            return LLM_YIELD_RESULT_WITHOUT_API(name, info)
        else:
            raise RuntimeError("Invalid Options for debug provider")
    raise RuntimeError("No valid option provided")
        