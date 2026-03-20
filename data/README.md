# Dataset Documentation

## Format

Each `.jsonl` file contains one document per line:

```json
{
  "id": "string — unique sample identifier",
  "text": "string — the input text",
  "source": "string — dataset source",
  "license": "string — license of the source data",
  "annotations": [
    {
      "start": 0,
      "end": 10,
      "text": "exact text at [start:end]",
      "entity_type": "PERSON | EMAIL | PHONE | SSN | CREDIT_CARD | LOCATION | NPI | MRN | ORGANIZATION",
      "difficulty": "standard | ambiguous | contextual | adversarial"
    }
  ],
  "metadata": {
    "category": "standard | ambiguous | contextual | adversarial",
    "domain": "general | healthcare | finance | ...",
    "ambiguity_score": 0.0
  }
}
```

Contextual samples additionally include a `context_pair` field linking to the paired sample ID.

## Categories

| Category | Samples | Description |
|----------|:-------:|-------------|
| Standard | 500 | Clear, unambiguous PII. Baseline — all systems should score well. |
| Ambiguous | 300 | Same string could be multiple entity types. Tests disambiguation. |
| Contextual | 200 | Paired samples: same string, different labels. Used for CSS. |
| Adversarial | 200 | Edge cases: international formats, obfuscation, code blocks, noisy text. |

## Entity Types

| Type | Description |
|------|------------|
| PERSON | Person name |
| EMAIL | Email address |
| PHONE | Phone number |
| SSN | US Social Security Number |
| CREDIT_CARD | Credit/debit card number |
| LOCATION | Geographic location, place name, or address |
| NPI | National Provider Identifier (healthcare, 10-digit) |
| MRN | Medical Record Number |
| ORGANIZATION | Organization or company name |

## Sources & Licenses

All samples are synthetic or sourced from permissively licensed datasets.
No real PII is included — all person names, emails, SSNs, etc. are fictional.

| Source | License | Samples Used | Categories |
|--------|---------|:------------:|------------|
| ai4privacy/pii-masking-300k | Apache 2.0 | ~400 | Standard |
| Gretel PII EN | Apache 2.0 | ~100 | Standard |
| Curated ambiguous corpus | CC0 | ~140 | Ambiguous |
| LLM-augmented ambiguous corpus | CC0 | ~160 | Ambiguous |
| OntoNotes 5.0 | LDC User Agreement | ~80 | Contextual (auto-paired) |
| Few-NERD | CC BY-SA 4.0 | ~50 | Contextual (auto-paired) |
| WNUT 2017 | CC BY 4.0 | ~55 | Contextual, Adversarial |
| WikiANN | CC BY-SA 3.0 | ~50 | Adversarial (international) |
| Gretel Finance | Apache 2.0 | ~40 | Adversarial (financial) |
| Healthcare PII corpus | CC0 | ~40 | Adversarial (medical) |
| NVIDIA Nemotron PII | Apache 2.0 | ~18 | Adversarial (multi-entity) |
| Hand-crafted | CC0 | ~67 | All categories |

## Validation

Run `python scripts/validate_dataset.py` to check all dataset files against the schema.

## Assembly

The dataset is assembled from source corpora using `python scripts/assemble_dataset.py`.
Source data is not included in this repository. The assembled dataset in `data/` is ready to use.
