import os
import time

import httpx

from adapters.base import PIIDetectorAdapter, DetectedEntity

# AmbientMeta entity type → benchmark normalized type
_AM_TYPE_MAP: dict[str, str | None] = {
    "PERSON": "PERSON",
    "EMAIL": "EMAIL",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE": "PHONE",
    "PHONE_NUMBER": "PHONE",
    "SSN": "SSN",
    "CREDIT_CARD": "CREDIT_CARD",
    "LOCATION": "LOCATION",
    "ADDRESS": "LOCATION",
    "NPI": "NPI",
    "MRN": "MRN",
    "ORGANIZATION": "ORGANIZATION",
    "ORG": "ORGANIZATION",
    # Skip types not in benchmark entity set
    "DATE_OF_BIRTH": None,
    "DOB": None,
    "IP_ADDRESS": None,
    "URL": None,
    "CREDENTIALS": None,
    "DEA": None,
    "DEA_NUMBER": None,
    "BANK_ROUTING_NUMBER": None,
    "REFERENCE_ID": None,
}


class AmbientMetaAdapter(PIIDetectorAdapter):
    """AmbientMeta Privacy Guard API adapter."""

    def __init__(self):
        self._client: httpx.Client | None = None
        self._api_key: str = ""
        self._api_url: str = ""

    def name(self) -> str:
        return "AmbientMeta Privacy Guard"

    def setup(self) -> None:
        self._api_key = os.environ.get("AMBIENTMETA_API_KEY", "")
        if not self._api_key:
            raise RuntimeError(
                "AMBIENTMETA_API_KEY environment variable is required for the AmbientMeta adapter"
            )
        self._api_url = os.environ.get(
            "AMBIENTMETA_API_URL", "https://api.ambientmeta.com/v1"
        ).rstrip("/")
        self._client = httpx.Client(
            base_url=self._api_url,
            headers={"X-API-Key": self._api_key},
            timeout=30.0,
        )

    def detect(self, text: str) -> list[DetectedEntity]:
        if self._client is None:
            raise RuntimeError("Call setup() before detect()")

        for attempt in range(3):
            response = self._client.post(
                "/sanitize",
                json={
                    "text": text,
                    "mode": "sanitize",
                    "config": {"confidence_threshold": 0.0},
                },
            )
            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", 2))
                time.sleep(wait)
                continue
            response.raise_for_status()
            break
        else:
            return []

        data = response.json()

        results: list[DetectedEntity] = []
        for entity in data.get("entities", []):
            raw_type = entity.get("type", "")
            normalized = _AM_TYPE_MAP.get(raw_type, raw_type)
            if normalized is None:
                continue
            start = entity.get("start", 0)
            end = entity.get("end", 0)
            results.append(
                DetectedEntity(
                    start=start,
                    end=end,
                    text=text[start:end],
                    entity_type=normalized,
                    confidence=entity.get("confidence", 0.0),
                )
            )
        results.sort(key=lambda e: e.start)
        return results

    def teardown(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
