from abc import ABC, abstractmethod

class FLTechnique(ABC):
    def __init__(self, name: str, **kwargs) -> None:
        self.name = name

    @abstractmethod
    def get_fault_localization(self, file: Path) -> list[int]:
        pass