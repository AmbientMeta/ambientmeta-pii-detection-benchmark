# PII Detection Benchmark

> Measuring what matters: not just whether PII is found, but whether your detector understands *context*.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Dataset](https://img.shields.io/badge/samples-1%2C200-green.svg)](#dataset)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

## Quick Results

| System | Overall F1 | Standard F1 | Ambiguous F1 | CSS | Adversarial F1 |
|--------|:---------:|:-----------:|:------------:|:---:|:--------------:|
| **AmbientMeta Privacy Guard** | **44.3%** | 40.5% | **44.4%** | **50.0%** | **54.0%** |
| Microsoft Presidio | **44.3%** | **45.8%** | 39.6% | 37.0% | 51.7% |
| spaCy NER | 30.0% | 21.3% | 37.2% | 40.5% | 37.3% |
| Regex Only | 24.4% | 31.4% | 6.8% | 3.0% | 28.0% |

> **Headline:** AmbientMeta's Context Sensitivity Score is **50.0%** — 13 points ahead of Presidio (37.0%) and 10 points ahead of spaCy NER (40.5%). Regex scores 3.0% because it literally cannot vary by context.

### Per-Entity F1

| Entity Type | AmbientMeta | Presidio | spaCy NER | Regex |
|-------------|:-----------:|:--------:|:---------:|:-----:|
| PERSON | **60.9%** | 59.4% | 59.4% | 0.0% |
| EMAIL | 95.5% | **98.2%** | 0.0% | 95.0% |
| PHONE | **75.8%** | 52.6% | 0.0% | 53.3% |
| SSN | **55.9%** | 44.1% | 0.0% | 44.7% |
| CREDIT_CARD | 14.3% | 10.0% | 0.0% | **40.9%** |
| LOCATION | **37.6%** | 31.0% | 31.0% | 0.0% |
| NPI | **7.8%** | 0.0% | 0.0% | 0.0% |
| ORGANIZATION | **13.4%** | 0.0% | 12.9% | 0.0% |

AmbientMeta is the **only system that detects NPI** (National Provider Identifiers) — a critical entity type for healthcare privacy compliance.

### Latency (Server-Side Processing)

| System | p50 | p95 | p99 |
|--------|:---:|:---:|:---:|
| Regex Only | <1ms | <1ms | <1ms |
| spaCy NER | 5.6ms | 13.1ms | 15.6ms |
| Microsoft Presidio | 9.7ms | 25.6ms | 29.7ms |
| AmbientMeta | 14.2ms | 22.8ms | 31.5ms |

> AmbientMeta latency reflects server-side `processing_ms` (actual detection time), not network round-trip. All systems are within production-viable bounds.

---

## What is Context Sensitivity Score (CSS)?

Most PII detectors can find an email address or SSN. But can they tell the difference between "Jordan" the person and "Jordan" the country? Between a phone number and a National Provider Identifier in a medical record?

**Context Sensitivity Score** measures a system's ability to correctly classify the *same string* differently based on surrounding context. It's computed on paired samples where identical text appears in two documents with different ground-truth labels.

### How CSS works

For each context pair:

| Outcome | Score | Example |
|---------|:-----:|---------|
| **Correct** — system classifies the string correctly in *both* contexts | +1.0 | Detects "Jordan" as PERSON in "Jordan presented results..." AND as LOCATION in "...arrived in Jordan yesterday" |
| **Partial** — system gets one context right, misses the other | +0.5 | Detects "Jordan" as PERSON in one context but also classifies it as PERSON in the location context |
| **Incorrect** — system misses both or classifies both the same | 0.0 | Labels "Jordan" as LOCATION in both contexts |

```
CSS = (correct + 0.5 × partial) / total_pairs
```

A regex detector will always score **CSS ≈ 0%** — it literally cannot vary its output based on context. This single metric captures the gap between pattern matching and genuine PII understanding.

### Why CSS matters

In production, the same 10-digit number might be a phone number in a support ticket and an NPI in a medical referral. The same name might be a person in one document and a location in another. Systems that treat every match the same — regardless of context — generate false positives that erode user trust and create compliance gaps.

---

## Dataset

**1,200 samples** across 4 categories, sourced from public NER datasets and hand-crafted cases.

| Category | Samples | Description | Purpose |
|----------|:-------:|-------------|---------|
| **Standard** | 500 | Clear, unambiguous PII (SSN, email, phone, names) | Baseline — everyone should score well |
| **Ambiguous** | 300 | Same string could be multiple entity types | Tests disambiguation without paired context |
| **Contextual** | 200 | Paired samples: same string, different labels | CSS computation — the headline metric |
| **Adversarial** | 200 | International formats, obfuscation, code blocks, noisy text | Robustness under real-world messiness |

### Entity types

PERSON, EMAIL, PHONE, SSN, CREDIT_CARD, LOCATION, NPI, MRN, ORGANIZATION

### Sources

All samples are synthetic or sourced from permissively licensed datasets. No real PII is included.

| Source | License | Categories |
|--------|---------|------------|
| ai4privacy/pii-masking-300k | Apache 2.0 | Standard |
| Gretel PII datasets | Apache 2.0 | Standard, Adversarial |
| OntoNotes 5.0 | LDC | Contextual |
| Few-NERD | CC BY-SA 4.0 | Contextual |
| WNUT 2017 | CC BY 4.0 | Contextual, Adversarial |
| WikiANN | CC BY-SA 3.0 | Adversarial |
| Hand-crafted | CC0 | All categories |

Full documentation: [`data/README.md`](data/README.md)

---

## Reproduce These Results

```bash
git clone https://github.com/ambientmeta/ambientmeta-pii-detection-benchmark
cd ambientmeta-pii-detection-benchmark
pip install -e .
python -m spacy download en_core_web_lg
python run_benchmark.py
```

### Run without AmbientMeta

The benchmark is fully functional without an AmbientMeta API key. The AmbientMeta adapter is automatically skipped if no key is set.

```bash
python run_benchmark.py --adapter regex spacy presidio
```

### Run with AmbientMeta

```bash
export AMBIENTMETA_API_KEY=your_key_here
python run_benchmark.py
```

Get a free API key (1K requests/month) at [ambientmeta.com](https://ambientmeta.com).

### Run a single category

```bash
python run_benchmark.py --category contextual
python run_benchmark.py --adapter presidio --category standard ambiguous
```

---

## Methodology

### Span matching

Predictions are matched to ground truth using **IoU (Intersection over Union)** with a threshold of 0.5. A prediction is a true positive only if:

1. It overlaps a ground truth span with IoU ≥ 0.5
2. The predicted entity type matches the ground truth type

Each ground truth span matches at most one prediction (greedy, best IoU first).

### Metrics

| Metric | Scope | Definition |
|--------|-------|------------|
| **Precision** | Per-type + aggregate | TP / (TP + FP) |
| **Recall** | Per-type + aggregate | TP / (TP + FN) |
| **F1** | Per-type + aggregate | Harmonic mean of precision and recall |
| **CSS** | Contextual category only | Context pair accuracy (see above) |
| **Latency** | Per-adapter | p50, p95, p99 per-document timing |

### Reproducibility

- All dependency versions pinned in `pyproject.toml`
- Random seed = 42 for dataset sampling
- SHA-256 hashes of dataset files recorded in results
- System info (Python version, OS, hardware) captured in results JSON

---

## Add Your System

Implement the adapter interface:

```python
from adapters.base import PIIDetectorAdapter, DetectedEntity

class MyAdapter(PIIDetectorAdapter):
    def name(self) -> str:
        return "My PII Detector"

    def detect(self, text: str) -> list[DetectedEntity]:
        # Your detection logic
        return [
            DetectedEntity(
                start=0, end=10,
                text="John Smith",
                entity_type="PERSON",
                confidence=0.95
            )
        ]
```

Register it in `run_benchmark.py`:

```python
ALL_ADAPTERS["my_system"] = MyAdapter
```

Run:

```bash
python run_benchmark.py --adapter my_system
```

---

## About AmbientMeta

[AmbientMeta](https://ambientmeta.com) is the privacy layer for AI. We sanitize PII from text with context-aware, multi-tier detection that learns from your corrections.

- **Tier 1:** Regex + checksum validation (SSN, credit card, email, phone)
- **Tier 2:** NER (spaCy + Presidio) for names, locations, organizations
- **Tier 3:** Compiled disambiguation rules from user feedback
- **Tier 4:** LLM escalation for spans the deterministic system can't resolve

The benchmark numbers above reflect Tiers 1–3. Tier 4 (async LLM escalation) improves accuracy over time as the system learns — it's not captured in a single benchmark run.

**Try it free:** [ambientmeta.com](https://ambientmeta.com) — 1,000 requests/month on the free tier.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

Dataset samples are sourced from permissively licensed public datasets. See [`data/README.md`](data/README.md) for per-source licensing.
