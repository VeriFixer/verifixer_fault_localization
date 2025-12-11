from abc import ABC, abstractmethod
from pathlib import Path

class FaultLocalization(ABC):
    @abstractmethod
    def configure(self, **kwargs):
        pass

    @abstractmethod
    def get_fault_localization(self, file: Path) -> list[int]:
        pass


import random
class GiveRandomLine(FaultLocalization):
    def configure(self, **kwargs):
        pass
    

    def get_fault_localization(self, file: Path) -> list[int]:
        with open(file, "r") as f:
            lines = f.readlines()

        line_numbers = list(range(1, len(lines) + 1))
        random.shuffle(line_numbers)
        return line_numbers