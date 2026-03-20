from adapters.base import PIIDetectorAdapter, DetectedEntity

# spaCy entity label → benchmark normalized type
_SPACY_TYPE_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
    "ORG": "ORGANIZATION",
}


class SpacyNERAdapter(PIIDetectorAdapter):
    """spaCy NER standalone — only the NER pipeline, no regex augmentation."""

    def __init__(self, model: str = "en_core_web_lg"):
        self._model_name = model
        self._nlp = None

    def name(self) -> str:
        return "spaCy NER"

    def setup(self) -> None:
        import spacy

        self._nlp = spacy.load(self._model_name, disable=["tagger", "parser", "lemmatizer"])

    def detect(self, text: str) -> list[DetectedEntity]:
        if self._nlp is None:
            raise RuntimeError("Call setup() before detect()")
        doc = self._nlp(text)
        results: list[DetectedEntity] = []
        for ent in doc.ents:
            normalized = _SPACY_TYPE_MAP.get(ent.label_)
            if normalized is None:
                continue
            results.append(
                DetectedEntity(
                    start=ent.start_char,
                    end=ent.end_char,
                    text=ent.text,
                    entity_type=normalized,
                    confidence=0.85,  # spaCy doesn't expose per-entity confidence
                )
            )
        return results

    def teardown(self) -> None:
        self._nlp = None
