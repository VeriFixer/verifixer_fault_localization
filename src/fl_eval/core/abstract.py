from abc import ABC, abstractmethod
from pathlib import Path

class FLTechnique(ABC):
    def __init__(self, name: str, **kwargs) -> None:
        self.name = name

    @abstractmethod
    def get_fault_localization(self, file: Path) -> list[int]:
        pass