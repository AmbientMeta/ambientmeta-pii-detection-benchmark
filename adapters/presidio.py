from adapters.base import PIIDetectorAdapter, DetectedEntity

# Presidio entity type → benchmark normalized type
_PRESIDIO_TYPE_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "US_SSN": "SSN",
    "CREDIT_CARD": "CREDIT_CARD",
    "LOCATION": "LOCATION",
    "NRP": None,  # Nationality/religious/political — skip
    "DATE_TIME": None,
    "US_DRIVER_LICENSE": None,
    "US_PASSPORT": None,
    "US_BANK_NUMBER": None,
    "IP_ADDRESS": None,
    "URL": None,
    "IBAN_CODE": None,
    "MEDICAL_LICENSE": None,
    "UK_NHS": None,
    "US_ITIN": None,
    "SG_NRIC_FIN": None,
    "AU_ABN": None,
    "AU_ACN": None,
    "AU_TFN": None,
    "AU_MEDICARE": None,
    "IN_PAN": None,
    "IN_AADHAAR": None,
    "IN_VEHICLE_REGISTRATION": None,
    "IN_VOTER": None,
    "IN_PASSPORT": None,
    "CRYPTO": None,
    "ES_NIF": None,
    "IT_FISCAL_CODE": None,
    "IT_DRIVER_LICENSE": None,
    "IT_VAT_CODE": None,
    "IT_PASSPORT": None,
    "IT_IDENTITY_CARD": None,
    "PL_PESEL": None,
}


class PresidioAdapter(PIIDetectorAdapter):
    """Microsoft Presidio with all default recognizers enabled."""

    def __init__(self):
        self._analyzer = None

    def name(self) -> str:
        return "Microsoft Presidio"

    def setup(self) -> None:
        from presidio_analyzer import AnalyzerEngine

        self._analyzer = AnalyzerEngine()

    def detect(self, text: str) -> list[DetectedEntity]:
        if self._analyzer is None:
            raise RuntimeError("Call setup() before detect()")

        presidio_results = self._analyzer.analyze(text=text, language="en")
        results: list[DetectedEntity] = []
        for r in presidio_results:
            normalized = _PRESIDIO_TYPE_MAP.get(r.entity_type, r.entity_type)
            if normalized is None:
                continue
            results.append(
                DetectedEntity(
                    start=r.start,
                    end=r.end,
                    text=text[r.start : r.end],
                    entity_type=normalized,
                    confidence=r.score,
                )
            )
        results.sort(key=lambda e: e.start)
        return results

    def teardown(self) -> None:
        self._analyzer = None
