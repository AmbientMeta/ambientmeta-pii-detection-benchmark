# PII Detection Benchmark

> Measuring what matters: not just whether PII is found, but whether your detector understands *context*.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Dataset](https://img.shields.io/badge/samples-1%2C021-green.svg)](#dataset)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

## Quick Results

| System | Overall F1 | Standard F1 | Ambiguous F1 | CSS | Adversarial F1 |
|--------|:---------:|:-----------:|:------------:|:---:|:--------------:|
| **AmbientMeta Privacy Guard** | **86.5%** | **84.4%** | **91.2%** | **83.7%** | **87.1%** |
| AmbientMeta (previous, spaCy) | 77.8% | 79.8% | 73.3% | 73.9% | 79.6% |
| Microsoft Presidio | 56.8% | 60.1% | 63.0% | 45.6% | 52.7% |
| spaCy NER | 46.2% | 33.2% | 64.9% | 45.6% | 43.3% |
| Regex Only | 27.5% | 41.8% | 8.2% | 6.5% | 26.3% |

> **Headline:** AmbientMeta leads with **86.5% overall F1** — 30 points ahead of Presidio — and wins on **every entity type**. Context Sensitivity Score is **83.7%** — 38 points ahead of both Presidio and spaCy NER (45.6%). AmbientMeta is the only system that detects healthcare entities (NPI: 96.3%, MRN: 84.6%).

### Per-Entity F1

| Entity Type | AmbientMeta | Presidio | spaCy NER | Regex |
|-------------|:-----------:|:--------:|:---------:|:-----:|
| PERSON | **91.0%** | 71.2% | 71.2% | 0.0% |
| EMAIL | **100.0%** | 99.6% | 0.0% | 96.8% |
| PHONE | **81.9%** | 57.6% | 0.0% | 57.4% |
| SSN | **92.5%** | 72.9% | 0.0% | 85.7% |
| CREDIT_CARD | **92.6%** | 89.6% | 0.0% | 78.5% |
| LOCATION | **80.3%** | 48.9% | 48.9% | 0.0% |
| NPI | **96.3%** | 0.0% | 0.0% | 0.0% |
| MRN | **84.6%** | 0.0% | 0.0% | 0.0% |
| ORGANIZATION | **79.5%** | 0.0% | 41.7% | 0.0% |

AmbientMeta leads on **every entity type** — the NER-driven ones (PERSON, LOCATION, ORGANIZATION), the regex/checksum ones (EMAIL, PHONE, SSN, CREDIT_CARD), and is the **only system that detects NPI and MRN** — critical entity types for healthcare privacy compliance (HIPAA).

### Model evolution: spaCy → GLiNER

AmbientMeta's previous NER engine used a fine-tuned spaCy model. The current engine
replaces it with a fine-tuned [GLiNER](https://github.com/urchade/GLiNER) transformer.
Both rows below were measured on the **same** dataset, so the delta is purely the engine:

| | Previous (spaCy) | Current (GLiNER) | Δ |
|---|:---:|:---:|:---:|
| Overall F1 | 77.8% | **86.5%** | **+8.7** |
| ORGANIZATION | 53.0% | 79.5% | **+26.4** |
| LOCATION | 60.1% | 80.3% | **+20.2** |
| PERSON | 85.1% | 91.0% | +5.9 |
| CSS | 73.9% | 83.7% | +9.8 |
| Latency (p50) | 3.4ms | 36.6ms | +33ms |

The gains concentrate on the NER-driven types (ORGANIZATION, LOCATION) and on context
sensitivity. The cost is latency: the transformer is ~10× slower than spaCy on CPU.
EMAIL/SSN/PHONE/NPI/MRN are served by shared regex/checksum tiers and are largely
engine-independent.

### Latency (Server-Side Processing)

| System | p50 | p95 | p99 |
|--------|:---:|:---:|:---:|
| Regex Only | <1ms | <1ms | <1ms |
| spaCy NER | 3.1ms | 24.6ms | 28.5ms |
| Microsoft Presidio | 4.5ms | 35.6ms | 40.9ms |
| AmbientMeta | 36.7ms | 263.4ms | 365.6ms |

> AmbientMeta latency reflects server-side `processing_ms` (actual detection time), not network round-trip. The higher figures reflect GLiNER transformer (ONNX) inference on a single CPU worker in a local Docker container — not a tuned production deployment. Regex/checksum tiers run in <1ms; the NER tier dominates the cost.

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

**1,021 samples** across 4 categories, sourced from public NER datasets and hand-crafted cases.

| Category | Samples | Description | Purpose |
|----------|:-------:|-------------|---------|
| **Standard** | 473 | Clear, unambiguous PII (SSN, email, phone, names) | Baseline — everyone should score well |
| **Ambiguous** | 256 | Same string could be multiple entity types | Tests disambiguation without paired context |
| **Contextual** | 92 | 46 minimal pairs: same string, different labels | CSS computation — the headline metric |
| **Adversarial** | 200 | International formats, obfuscation, code blocks, noisy text | Robustness under real-world messiness |

> **Independent gold standard.** Ground-truth labels are decided by a written
> [annotation spec](docs/ANNOTATION_GUIDELINES.md) and the text alone — never derived
> from, or reconciled against, what any detector (AmbientMeta included) outputs. Labels
> were produced by blind double-annotation with deterministic adjudication. The contextual
> category keeps only genuine minimal pairs (same surface string, divergent ground-truth
> type); fabricated/incoherent samples were removed. See the spec for every ruling.

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

### Ground-truth annotation

Labels follow a written [annotation spec](docs/ANNOTATION_GUIDELINES.md), applied **blind
to every detector's output**. Each sample was independently double-annotated; agreements
form the gold standard and disagreements were adjudicated against the spec, with the free
local detectors (spaCy/Presidio) used only as tie-breaking signals — never as authority.
This decouples the ground truth from any system under test, including AmbientMeta.

### Reproducibility

- All dependency versions pinned in `pyproject.toml`
- SHA-256 hashes of dataset files recorded in results
- System info (Python version, OS, hardware) captured in results JSON
- AmbientMeta results above were produced against the engine running locally via
  `docker compose up` (GLiNER ONNX, single CPU worker) — fully reproducible, no API key
  to a hosted service required

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

- **Tier 1:** Regex + checksum validation (SSN, credit card, email, phone, NPI, MRN)
- **Tier 2:** NER via a fine-tuned [GLiNER](https://github.com/urchade/GLiNER) transformer (ONNX) for names, locations, and organizations
- **Tier 3:** Format-preserving sanitization and rehydration

The benchmark above runs against the deployed detection engine (Tiers 1–2) via the live `/v1/sanitize` API.

**Try it free:** [ambientmeta.com](https://ambientmeta.com) — 1,000 requests/month on the free tier.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

Dataset samples are sourced from permissively licensed public datasets. See [`data/README.md`](data/README.md) for per-source licensing.
