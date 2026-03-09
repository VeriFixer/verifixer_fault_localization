from fl_eval.core.abstract import FLTechnique 
from pathlib import Path

# Empty ranker in the score function is equivalent to 
# chosing on average the correct line in half the entries
# As the score function for the non selected lines returns the expected
# lines to test from the non tested lines for completness
class EmptyRanker(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_fault_localization(self, file: Path) -> list[int]:
        line_numbers: list[int] = []
        return line_numbers