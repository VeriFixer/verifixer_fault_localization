from pathlib import Path

from fl_eval.strategies.llm_base_ranker import LLMBaseRanker


class LLMErrMsgRanker(LLMBaseRanker):
    def build_extra_context(self, file: Path) -> str:
        return (
            "The following content is the raw output from running Dafny verify on the same file.\n"
            "Use this context to improve suspicious-line ranking.\n\n"
            f"{self.run_dafny_verify_raw(file)}"
        )