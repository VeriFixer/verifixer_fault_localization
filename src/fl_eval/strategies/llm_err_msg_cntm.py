from pathlib import Path
from typing import Any

from fl_eval.strategies.counter_example_if_reassume import CounterExampleIfReassume
from fl_eval.strategies.llm_base_ranker import LLMBaseRanker
from fl_eval.util.ranking_strategy import (
    DEFAULT_COUNTEREXAMPLE_RANKING_CONTROLS,
    CounterExampleRankingControls,
)
from logging_config import get_logger

logger = get_logger(__name__)


class LLMErrMsgCNTMRanker(LLMBaseRanker):
    def __init__(
        self,
        name: str,
        ranking_controls: CounterExampleRankingControls = DEFAULT_COUNTEREXAMPLE_RANKING_CONTROLS,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.cntm_ranker = CounterExampleIfReassume(
            name="CNTM",
            ranking_controls=ranking_controls,
        )

    def build_extra_context(self, file: Path) -> str:
        cntm_ranked_lines: list[int]
        try:
            cntm_ranked_lines = self.cntm_ranker.get_fault_localization(file)
        except Exception as ex:
            logger.warning("CNTM ranking failed for %s: %s", file.name, ex)
            cntm_ranked_lines = []

        return (
            "The following content is context for the same file:\n"
            "1) Raw output from Dafny verify\n"
            f"{self.run_dafny_verify_raw(file)}\n\n"
            "2) Another technique produced the following ranking, which you may use as guidance (but not as a constraint)\n"
            f"{cntm_ranked_lines}\n"
        )