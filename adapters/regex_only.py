import re

from adapters.base import PIIDetectorAdapter, DetectedEntity

# Pure regex patterns — no ML, no NER, no context.
# This is the floor: shows what you get with zero intelligence.

_PATTERNS: dict[str, re.Pattern] = {
    "SSN": re.compile(
        r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"
    ),
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "CREDIT_CARD": re.compile(
        r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))"
        r"[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,4}\b"
    ),
    "PHONE": re.compile(
        r"(?<!\d)"
        r"(?:\+?1[-.\s]?)?"
        r"(?:\(?\d{3}\)?[-.\s]?)"
        r"\d{3}[-.\s]?\d{4}"
        r"(?!\d)"
    ),
}


class RegexOnlyAdapter(PIIDetectorAdapter):
    """Pure regex baseline — no NER, no ML, no context awareness."""

    def name(self) -> str:
        return "Regex Only"

    def detect(self, text: str) -> list[DetectedEntity]:
        results: list[DetectedEntity] = []
        for entity_type, pattern in _PATTERNS.items():
            for match in pattern.finditer(text):
                results.append(
                    DetectedEntity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        entity_type=entity_type,
                        confidence=1.0,
                    )
                )
        results.sort(key=lambda e: e.start)
        return results
