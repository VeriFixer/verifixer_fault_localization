from pathlib import Path
import random
from fl_eval.core.abstract import FLTechnique # Import ABC

class RandomRanker(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_fault_localization(self, file: Path) -> list[int]:
        with open(file, "r") as f:
            lines = f.readlines()

        line_numbers = list(range(1, len(lines) + 1))
        random.shuffle(line_numbers)
        return line_numbers
    