from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any, cast

import config as gl
import fl_eval.execution.external_cmd as run_cmd
from fl_eval.core.abstract import FLTechnique
from fl_eval.llm.llm_configurations import LLM
from fl_eval.llm.llm_configurations import MODEL_REGISTRY
from fl_eval.llm.llm_create import create_llm
from logging_config import get_logger

logger = get_logger(__name__)

LLM_MODEL_CHOICES = list(MODEL_REGISTRY.keys())

TECHNIQUE_TO_LLM_MODEL: dict[str, str] = {
    "LLM_NO_API": "without_api",
    "LLM": os.getenv("LLM_REAL_MODEL_NAME", "cost_stub_all_lines_ranked"),
    "LLM_ERR_MSG": os.getenv("LLM_REAL_MODEL_NAME", "cost_stub_all_lines_ranked"),
    "LLM_ERR_MSG_CNTM": os.getenv("LLM_REAL_MODEL_NAME", "cost_stub_all_lines_ranked"),
}


class LLMBaseRanker(FLTechnique):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        if name == "LLM_NO_API":
            self.suppress_scope_warnings = True

        selected_model = TECHNIQUE_TO_LLM_MODEL.get(name)
        if selected_model is None:
            candidate = kwargs.get("llm_model", "cost_stub_all_lines_ranked")
            selected_model = candidate if isinstance(candidate, str) else "cost_stub_all_lines_ranked"
        self.llm_model_name: str = selected_model
        if self.llm_model_name not in LLM_MODEL_CHOICES:
            raise ValueError("llm_model must be one of: " + ", ".join(LLM_MODEL_CHOICES))

        self.verbose = bool(kwargs.get("verbose", False))
        self.llm: LLM = create_llm(
            f"{name}:{self.llm_model_name}", self.llm_model_name, verbose=self.verbose
        )
        self.dafny = os.environ.get("DAFNY_EXEC") or "dafny"

    def get_costs(self) -> None:
        self.llm.get_my_cost_statisitcs()

    def get_cost_snapshot(self) -> dict[str, str | int | float]:
        return self.llm.get_cost_snapshot().to_metadata_dict()

    def build_extra_context(self, file: Path) -> str:
        return ""

    def run_dafny_verify_raw(self, file: Path) -> str:
        command: list[str] = [
            self.dafny,
            "verify",
            str(file),
            "--allow-warnings",
            "--verification-time-limit",
            str(gl.MAX_TIME_EXTERNAL_PROGRAMS),
            f"--solver-option:O:memory_max_size={gl.MAX_RAM_EXTERNAL_PROGRAMS * 1000}",
        ]

        status, stdout, stderr = run_cmd.run_external_cmd(command)
        return (
            "BEGIN_RAW_DAFNY_VERIFY_OUTPUT\n"
            f"STATUS: {status.name}\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}\n"
            "END_RAW_DAFNY_VERIFY_OUTPUT"
        )

    def _format_prompt(self, file: Path, total_lines: int) -> str:
        lines = file.read_text(encoding="utf-8").splitlines()
        numbered_lines = "\n".join(f"{idx}: {line}" for idx, line in enumerate(lines, start=1))
        extra_context = self.build_extra_context(file)
        context_tail = ""
        if extra_context:
            context_tail = f"\n\nADDITIONAL_CONTEXT\n{extra_context}\nEND_ADDITIONAL_CONTEXT"

        return (
            "You are a fault-localization model.\n"
            "Rank suspicious lines from most likely fault to least likely fault.\n"
            "Output contract (strict):\n"
            "1) The list is a ranking: the first element must be the line most likely to contain the fault.\n"
            "2) You do not have to return a full list with all the lines prefer shorter lists.\n"
            "3) Return exactly one JSON array of unique 1-based line numbers.\n"
            "4) Do not return any explanation, markdown, code fences, labels, or extra text.\n"
            "5) Use only integers in the inclusive range [1, total_lines].\n"
            "6) If no suspicious lines are found, return [].\n"
            "7) Your entire response must match this pattern: ^\\[(?:\\s*\\d+\\s*(?:,\\s*\\d+\\s*)*)?\\]$\n"
            "Example valid response: [30, 15, 29]\n"
            f"The file has {total_lines} lines.\n"
            "BEGIN_FILE\n"
            f"{numbered_lines}\n"
            f"END_FILE{context_tail}"
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
        self.llm.reset_chat_history()
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