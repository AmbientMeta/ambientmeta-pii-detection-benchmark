from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DetectedEntity:
    start: int
    end: int
    text: str
    entity_type: str
    confidence: float  # 0.0 - 1.0


class PIIDetectorAdapter(ABC):
    """Base adapter interface for PII detection systems."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable system name for results display."""
        ...

    @abstractmethod
    def detect(self, text: str) -> list[DetectedEntity]:
        """Run PII detection on input text. Return detected entities."""
        ...

    def setup(self) -> None:
        """Optional one-time setup (model loading, API client init, etc.)."""
        pass

    def teardown(self) -> None:
        """Optional cleanup."""
        pass
