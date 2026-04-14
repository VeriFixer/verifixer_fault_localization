from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, cast

from fl_eval.core.abstract import FLTechnique
from fl_eval.llm.llm_create import create_llm
from fl_eval.llm.llm_configurations import LLM
from logging_config import get_logger

logger = get_logger(__name__)

LLM_MODEL_CHOICES = [
    "cost_stub_all_lines_ranked",
    "without_api",
    "deepseek-r1",
    "qwen3-coder-480b",
    "qwen3-coder-30b",
    "llama-3.1-8b-instruct-free",
    "qwen2.5-7b-instruct-free",
]

TECHNIQUE_TO_LLM_MODEL: dict[str, str] = {
    "llm_stub_all_lines_ranked": "cost_stub_all_lines_ranked",
    "llm_without_api": "without_api",
    "llm_qwen_480b": "qwen3-coder-480b",
}


class LLMRanker(FLTechnique):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        if(name == "llm_stub_all_lines_ranked"):
            self.suppress_scope_warnings: bool = True
        selected_model = TECHNIQUE_TO_LLM_MODEL.get(name)
        if selected_model is None:
            candidate = kwargs.get("llm_model", "cost_stub_all_lines_ranked")
            selected_model = candidate if isinstance(candidate, str) else "cost_stub_all_lines_ranked"
        self.llm_model_name: str = selected_model
        if self.llm_model_name not in LLM_MODEL_CHOICES:
            raise ValueError(
                "llm_model must be one of: " + ", ".join(LLM_MODEL_CHOICES)
            )

        self.verbose = bool(kwargs.get("verbose", False))
        self.llm: LLM = create_llm(
            f"{name}:{self.llm_model_name}", self.llm_model_name, verbose=self.verbose
        )

    def get_costs(self) -> None:
        self.llm.get_my_cost_statisitcs()

    def _format_prompt(self, file: Path, total_lines: int) -> str:
        lines = file.read_text(encoding="utf-8").splitlines()
        numbered_lines = "\n".join(f"{idx}: {line}" for idx, line in enumerate(lines, start=1))

        return (
            "You are a fault-localization model.\n"
            "Rank suspicious lines from most likely fault to least likely fault.\n"
            "Return only a JSON array of unique 1-based line numbers.\n"
            f"The file has {total_lines} lines.\n"
            "BEGIN_FILE\n"
            f"{numbered_lines}\n"
            "END_FILE"
        )

    def _parse_predictions(self, response: str, total_lines: int) -> list[int]:
        raw: Any
        try:
            raw = json.loads(response)
        except json.JSONDecodeError:
            try:
                raw = ast.literal_eval(response)
            except (ValueError, SyntaxError):
                raw = []

        if not isinstance(raw, list):
            return []

        raw_items = cast(list[object], raw)
        ranked_lines: list[int] = []
        for item in raw_items:
            if isinstance(item, int) and 1 <= item <= total_lines and item not in ranked_lines:
                ranked_lines.append(item)

        return ranked_lines

    def get_fault_localization(self, file: Path) -> list[int]:
        if not file.is_file():
            raise FileNotFoundError(f"File does not exist: {file}")

        lines = file.read_text(encoding="utf-8").splitlines()
        if not lines:
            return []

        prompt = self._format_prompt(file, len(lines))
        response = self.llm.get_response(prompt)
        predictions = self._parse_predictions(response, len(lines))

        if predictions:
            return predictions

        logger.warning(
            "LLM model %s returned no valid predictions for %s; Giving back empty answer",
            self.llm_model_name,
            file.name,
        )
        return []