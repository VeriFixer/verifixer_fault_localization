from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

class FLTechnique(ABC):
    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name

    @abstractmethod
    def get_fault_localization(self, file: Path) -> list[int]:
        pass