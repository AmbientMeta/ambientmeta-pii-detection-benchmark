#!/usr/bin/env python3
"""Assemble the benchmark dataset from calibration-data sources.

Reads from ~/.ambientmeta/calibration-data/*, normalizes to benchmark schema,
samples target counts per category, and writes to data/*.jsonl.

Usage:
    python scripts/assemble_dataset.py
    python scripts/assemble_dataset.py --source-dir /path/to/calibration-data
    python scripts/assemble_dataset.py --dry-run  # show counts without writing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Benchmark normalized entity types
BENCHMARK_TYPES = {
    "PERSON", "EMAIL", "PHONE", "SSN", "CREDIT_CARD", "LOCATION",
    "NPI", "MRN", "ORGANIZATION", "ADDRESS",
}

# Map from source entity types → benchmark types
TYPE_MAP: dict[str, str | None] = {
    # Standard mappings
    "PERSON": "PERSON",
    "EMAIL_ADDRESS": "EMAIL",
    "EMAIL": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "PHONE": "PHONE",
    "SSN": "SSN",
    "US_SSN": "SSN",
    "CREDIT_CARD": "CREDIT_CARD",
    "LOCATION": "LOCATION",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
    "ADDRESS": "LOCATION",
    "NPI": "NPI",
    "MRN": "MRN",
    "ORGANIZATION": "ORGANIZATION",
    "ORG": "ORGANIZATION",
    # Skip these
    "REFERENCE_ID": None,
    "DATE_OF_BIRTH": None,
    "CREDENTIALS": None,
    "IP_ADDRESS": None,
    "URL": None,
    "DEA_NUMBER": None,
    "BANK_ROUTING_NUMBER": None,
    "NRP": None,
    "DATE_TIME": None,
    "NORP": None,
    "EVENT": None,
    "WORK_OF_ART": None,
    "LAW": None,
    "LANGUAGE": None,
    "PRODUCT": None,
    "QUANTITY": None,
    "ORDINAL": None,
    "CARDINAL": None,
    "MONEY": None,
    "PERCENT": None,
    "TIME": None,
    "DATE": None,
}

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_SOURCE = Path.home() / ".ambientmeta" / "calibration-data"

# Target sample counts per category
TARGETS = {
    "standard": 500,
    "ambiguous": 300,
    "contextual": 200,  # ~100 pairs
    "adversarial": 200,
}


def load_source(source_dir: Path, name: str) -> list[dict]:
    """Load a source corpus.jsonl file."""
    path = source_dir / name / "corpus.jsonl"
    if not path.exists():
        print(f"  [SKIP] {name}: corpus.jsonl not found")
        return []
    samples = []
    for line in path.read_text().strip().splitlines():
        if line.strip():
            samples.append(json.loads(line))
    return samples


def normalize_entity(entity: dict) -> dict | None:
    """Normalize a source entity to benchmark format. Returns None if type should be skipped."""
    src_type = entity.get("type", "")
    normalized = TYPE_MAP.get(src_type)
    if normalized is None:
        return None
    return {
        "start": entity["start"],
        "end": entity["end"],
        "text": entity["text"],
        "entity_type": normalized,
    }


def normalize_sample(
    sample: dict,
    source_name: str,
    category: str,
    difficulty: str,
    idx: int,
    domain: str = "general",
    ambiguity_score: float = 0.0,
) -> dict | None:
    """Normalize a source sample to benchmark format."""
    text = sample.get("text", "")
    if not text or len(text) < 10:
        return None

    entities = []
    for e in sample.get("entities", []):
        normalized = normalize_entity(e)
        if normalized:
            # Validate span
            actual = text[normalized["start"]:normalized["end"]]
            if actual != normalized["text"]:
                continue
            normalized["difficulty"] = difficulty
            entities.append(normalized)

    if not entities:
        return None

    prefix = category[:3]
    sample_id = f"{prefix}-{source_name[:6]}-{idx:04d}"

    return {
        "id": sample_id,
        "text": text,
        "source": source_name,
        "license": "CC0",
        "annotations": entities,
        "metadata": {
            "category": category,
            "domain": domain,
            "ambiguity_score": ambiguity_score,
        },
    }


def has_benchmark_entities(sample: dict) -> bool:
    """Check if a source sample has any entities that map to benchmark types."""
    for e in sample.get("entities", []):
        if TYPE_MAP.get(e.get("type")) is not None:
            return True
    return False


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def is_natural_text(text: str) -> bool:
    """Filter out overly synthetic/robotic text."""
    if len(text) < 20:
        return False
    if len(text) > 2000:
        return False
    # Must have at least some words
    words = text.split()
    if len(words) < 4:
        return False
    return True


# ─── Category 1: Standard ───────────────────────────────────────────────

def assemble_standard(source_dir: Path) -> list[dict]:
    """Assemble standard category from clear, unambiguous sources."""
    print("\n[Standard] Assembling...")
    candidates: list[dict] = []
    seen_hashes: set[str] = set()

    # Target entity type balance
    type_counts: Counter = Counter()
    type_limits = {
        "PERSON": 120, "EMAIL": 80, "PHONE": 80, "SSN": 60,
        "CREDIT_CARD": 60, "LOCATION": 100,
    }

    sources = [
        ("ai4privacy", "general"),
        ("gretel_pii_en", "general"),
        ("kaggle_pii_7k", "general"),
        ("nemotron_pii", "general"),
        ("synthetic", "general"),
    ]

    for src_name, domain in sources:
        samples = load_source(source_dir, src_name)
        random.shuffle(samples)
        added = 0

        for sample in samples:
            if not has_benchmark_entities(sample) or not is_natural_text(sample["text"]):
                continue

            h = text_hash(sample["text"])
            if h in seen_hashes:
                continue

            # Check if we still need entities of these types
            sample_types = set()
            for e in sample.get("entities", []):
                mapped = TYPE_MAP.get(e.get("type"))
                if mapped and mapped in type_limits:
                    sample_types.add(mapped)

            # Skip if all entity types in this sample are already at limit
            needed = any(type_counts[t] < type_limits.get(t, 999) for t in sample_types)
            if not needed and sample_types:
                continue

            normalized = normalize_sample(
                sample, src_name, "standard", "standard",
                len(candidates), domain=domain
            )
            if normalized and normalized["annotations"]:
                seen_hashes.add(h)
                candidates.append(normalized)
                for ann in normalized["annotations"]:
                    type_counts[ann["entity_type"]] += 1
                added += 1

            if len(candidates) >= TARGETS["standard"]:
                break

        print(f"  {src_name}: added {added} samples")
        if len(candidates) >= TARGETS["standard"]:
            break

    print(f"  Total: {len(candidates)} samples")
    print(f"  Type distribution: {dict(type_counts)}")
    return candidates[:TARGETS["standard"]]


# ─── Category 2: Ambiguous ───────────────────────────────────────────────

def assemble_ambiguous(source_dir: Path) -> list[dict]:
    """Assemble ambiguous category from curated ambiguous sources."""
    print("\n[Ambiguous] Assembling...")
    candidates: list[dict] = []
    seen_hashes: set[str] = set()

    # Primary: pre-curated ambiguous datasets
    for src_name in ["ambiguous", "ambiguous_llm"]:
        samples = load_source(source_dir, src_name)
        random.shuffle(samples)
        added = 0

        for sample in samples:
            if not has_benchmark_entities(sample) or not is_natural_text(sample["text"]):
                continue

            h = text_hash(sample["text"])
            if h in seen_hashes:
                continue

            normalized = normalize_sample(
                sample, src_name, "ambiguous", "ambiguous",
                len(candidates), ambiguity_score=0.7
            )
            if normalized and normalized["annotations"]:
                seen_hashes.add(h)
                candidates.append(normalized)
                added += 1

            if len(candidates) >= TARGETS["ambiguous"]:
                break

        print(f"  {src_name}: added {added} samples")
        if len(candidates) >= TARGETS["ambiguous"]:
            break

    # Secondary: healthcare NPI/PHONE overlap cases
    if len(candidates) < TARGETS["ambiguous"]:
        samples = load_source(source_dir, "healthcare")
        random.shuffle(samples)
        added = 0

        for sample in samples:
            # Look for samples with NPI or PHONE that could be ambiguous
            types_present = {e.get("type") for e in sample.get("entities", [])}
            has_npi_phone = types_present & {"NPI", "PHONE_NUMBER"}
            if not has_npi_phone or not is_natural_text(sample["text"]):
                continue

            h = text_hash(sample["text"])
            if h in seen_hashes:
                continue

            normalized = normalize_sample(
                sample, "healthcare", "ambiguous", "ambiguous",
                len(candidates), domain="healthcare", ambiguity_score=0.8
            )
            if normalized and normalized["annotations"]:
                seen_hashes.add(h)
                candidates.append(normalized)
                added += 1

            if len(candidates) >= TARGETS["ambiguous"]:
                break

        print(f"  healthcare: added {added} samples")

    print(f"  Total: {len(candidates)} samples")
    return candidates[:TARGETS["ambiguous"]]


# ─── Category 3: Contextual (Paired) ────────────────────────────────────

def find_context_pairs(source_dir: Path) -> list[dict]:
    """Find same-string different-label pairs across NER datasets."""
    print("\n[Contextual] Finding context pairs...")

    # Collect all (text_of_entity, entity_type, sample) triples
    entity_index: dict[str, list[tuple[str, dict]]] = defaultdict(list)

    for src_name in ["ontonotes5", "few_nerd", "wnut17"]:
        samples = load_source(source_dir, src_name)
        for sample in samples:
            if not is_natural_text(sample["text"]):
                continue
            for e in sample.get("entities", []):
                mapped = TYPE_MAP.get(e.get("type"))
                if mapped and mapped in {"PERSON", "LOCATION", "ORGANIZATION"}:
                    key = e["text"].lower().strip()
                    if len(key) >= 3:  # Skip very short entity names
                        entity_index[key].append((mapped, sample))

    # Find entities that appear with different types
    pairs: list[dict] = []
    pair_idx = 0
    used_samples: set[str] = set()

    for entity_text, occurrences in entity_index.items():
        # Group by type
        by_type: dict[str, list[dict]] = defaultdict(list)
        for etype, sample in occurrences:
            by_type[etype].append(sample)

        if len(by_type) < 2:
            continue

        # Create pairs from different types
        types = list(by_type.keys())
        for i in range(len(types)):
            for j in range(i + 1, len(types)):
                type_a = types[i]
                type_b = types[j]
                samples_a = by_type[type_a]
                samples_b = by_type[type_b]

                for sa in samples_a:
                    sa_id = sa.get("document_id", "")
                    if sa_id in used_samples:
                        continue
                    for sb in samples_b:
                        sb_id = sb.get("document_id", "")
                        if sb_id in used_samples or sb_id == sa_id:
                            continue

                        # Found a valid pair
                        id_a = f"ctx-{pair_idx:04d}a"
                        id_b = f"ctx-{pair_idx:04d}b"

                        # Find the entity annotation in each sample
                        ann_a = _find_entity_in_sample(sa, entity_text, type_a)
                        ann_b = _find_entity_in_sample(sb, entity_text, type_b)
                        if ann_a is None or ann_b is None:
                            continue

                        pair_a = {
                            "id": id_a,
                            "text": sa["text"],
                            "source": "context_pair",
                            "license": "CC0",
                            "context_pair": id_b,
                            "annotations": [{
                                "start": ann_a["start"],
                                "end": ann_a["end"],
                                "text": ann_a["text"],
                                "entity_type": type_a,
                                "difficulty": "contextual",
                            }],
                            "metadata": {
                                "category": "contextual",
                                "domain": "general",
                                "ambiguity_score": 0.8,
                            },
                        }
                        pair_b = {
                            "id": id_b,
                            "text": sb["text"],
                            "source": "context_pair",
                            "license": "CC0",
                            "context_pair": id_a,
                            "annotations": [{
                                "start": ann_b["start"],
                                "end": ann_b["end"],
                                "text": ann_b["text"],
                                "entity_type": type_b,
                                "difficulty": "contextual",
                            }],
                            "metadata": {
                                "category": "contextual",
                                "domain": "general",
                                "ambiguity_score": 0.8,
                            },
                        }

                        pairs.append(pair_a)
                        pairs.append(pair_b)
                        used_samples.add(sa_id)
                        used_samples.add(sb_id)
                        pair_idx += 1

                        if pair_idx >= TARGETS["contextual"] // 2:
                            return pairs

                        break  # One pair per sample_a
                    if pair_idx >= TARGETS["contextual"] // 2:
                        break
                if pair_idx >= TARGETS["contextual"] // 2:
                    break
            if pair_idx >= TARGETS["contextual"] // 2:
                break

    return pairs


def _find_entity_in_sample(sample: dict, entity_text: str, expected_type: str) -> dict | None:
    """Find a specific entity annotation in a sample."""
    for e in sample.get("entities", []):
        mapped = TYPE_MAP.get(e.get("type"))
        if mapped == expected_type and e["text"].lower().strip() == entity_text:
            return e
    return None


def assemble_contextual(source_dir: Path) -> list[dict]:
    """Assemble contextual category with paired samples."""
    pairs = find_context_pairs(source_dir)
    print(f"  Found {len(pairs) // 2} context pairs ({len(pairs)} samples)")

    # Add hand-crafted seed pairs (already in data/contextual/)
    existing = []
    existing_file = DATA_DIR / "contextual" / "contextual_detection.jsonl"
    if existing_file.exists():
        for line in existing_file.read_text().strip().splitlines():
            if line.strip():
                existing.append(json.loads(line))
        # Remove existing IDs from pairs to avoid conflicts
        existing_ids = {s["id"] for s in existing}
        pairs = [p for p in pairs if p["id"] not in existing_ids]

    # Combine: hand-crafted first, then auto-discovered
    combined = existing + pairs
    print(f"  Total: {len(combined)} samples ({len(existing)} hand-crafted + {len(pairs)} auto-discovered)")
    return combined[:TARGETS["contextual"]]


# ─── Category 4: Adversarial ────────────────────────────────────────────

def assemble_adversarial(source_dir: Path) -> list[dict]:
    """Assemble adversarial category from edge case sources."""
    print("\n[Adversarial] Assembling...")
    candidates: list[dict] = []
    seen_hashes: set[str] = set()

    # Keep existing hand-crafted adversarial samples
    existing_file = DATA_DIR / "adversarial" / "adversarial_cases.jsonl"
    if existing_file.exists():
        for line in existing_file.read_text().strip().splitlines():
            if line.strip():
                sample = json.loads(line)
                candidates.append(sample)
                seen_hashes.add(text_hash(sample["text"]))
        print(f"  existing hand-crafted: {len(candidates)} samples")

    # wikiann — international names and non-Latin scripts
    samples = load_source(source_dir, "wikiann")
    random.shuffle(samples)
    added = 0
    for sample in samples:
        if not has_benchmark_entities(sample):
            continue
        text = sample["text"]
        # Prefer non-ASCII text (international formats)
        if all(ord(c) < 128 for c in text):
            continue
        if not is_natural_text(text):
            continue

        h = text_hash(text)
        if h in seen_hashes:
            continue

        normalized = normalize_sample(
            sample, "wikiann", "adversarial", "adversarial",
            len(candidates), ambiguity_score=0.4
        )
        if normalized and normalized["annotations"]:
            seen_hashes.add(h)
            candidates.append(normalized)
            added += 1
        if added >= 50:
            break
    print(f"  wikiann (international): added {added} samples")

    # gretel_finance — domain-specific financial formats
    samples = load_source(source_dir, "gretel_finance")
    random.shuffle(samples)
    added = 0
    for sample in samples:
        if not has_benchmark_entities(sample) or not is_natural_text(sample["text"]):
            continue
        h = text_hash(sample["text"])
        if h in seen_hashes:
            continue

        normalized = normalize_sample(
            sample, "gretel_finance", "adversarial", "adversarial",
            len(candidates), domain="finance", ambiguity_score=0.3
        )
        if normalized and normalized["annotations"]:
            seen_hashes.add(h)
            candidates.append(normalized)
            added += 1
        if added >= 40:
            break
    print(f"  gretel_finance: added {added} samples")

    # healthcare — medical record formats
    samples = load_source(source_dir, "healthcare")
    random.shuffle(samples)
    added = 0
    for sample in samples:
        if not is_natural_text(sample["text"]):
            continue
        # Prefer samples with healthcare-specific entity types
        types = {e.get("type") for e in sample.get("entities", [])}
        if not types & {"NPI", "MRN", "DEA_NUMBER"}:
            continue

        h = text_hash(sample["text"])
        if h in seen_hashes:
            continue

        normalized = normalize_sample(
            sample, "healthcare", "adversarial", "adversarial",
            len(candidates), domain="healthcare", ambiguity_score=0.5
        )
        if normalized and normalized["annotations"]:
            seen_hashes.add(h)
            candidates.append(normalized)
            added += 1
        if added >= 40:
            break
    print(f"  healthcare: added {added} samples")

    # wnut17 — noisy social media text
    samples = load_source(source_dir, "wnut17")
    random.shuffle(samples)
    added = 0
    for sample in samples:
        if not has_benchmark_entities(sample) or not is_natural_text(sample["text"]):
            continue
        h = text_hash(sample["text"])
        if h in seen_hashes:
            continue

        normalized = normalize_sample(
            sample, "wnut17", "adversarial", "adversarial",
            len(candidates), ambiguity_score=0.4
        )
        if normalized and normalized["annotations"]:
            seen_hashes.add(h)
            candidates.append(normalized)
            added += 1
        if added >= 40:
            break
    print(f"  wnut17 (noisy): added {added} samples")

    # nemotron — general edge cases to fill remaining
    remaining = TARGETS["adversarial"] - len(candidates)
    if remaining > 0:
        samples = load_source(source_dir, "nemotron_pii")
        random.shuffle(samples)
        added = 0
        for sample in samples:
            if not has_benchmark_entities(sample) or not is_natural_text(sample["text"]):
                continue
            text = sample["text"]
            h = text_hash(text)
            if h in seen_hashes:
                continue

            # Prefer multi-entity samples (adversarial complexity)
            entity_count = sum(1 for e in sample.get("entities", []) if TYPE_MAP.get(e.get("type")))
            if entity_count < 2:
                continue

            normalized = normalize_sample(
                sample, "nemotron_pii", "adversarial", "adversarial",
                len(candidates), ambiguity_score=0.3
            )
            if normalized and normalized["annotations"]:
                seen_hashes.add(h)
                candidates.append(normalized)
                added += 1
            if added >= remaining:
                break
        print(f"  nemotron_pii (multi-entity): added {added} samples")

    print(f"  Total: {len(candidates)} samples")
    return candidates[:TARGETS["adversarial"]]


# ─── Main ────────────────────────────────────────────────────────────────

def write_category(category: str, samples: list[dict], dry_run: bool = False):
    """Write samples to the category's JSONL file."""
    if dry_run:
        print(f"  [DRY RUN] Would write {len(samples)} samples to data/{category}/")
        return

    out_dir = DATA_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine output filename
    filenames = {
        "standard": "standard_entities.jsonl",
        "ambiguous": "ambiguous_spans.jsonl",
        "contextual": "contextual_detection.jsonl",
        "adversarial": "adversarial_cases.jsonl",
    }
    out_file = out_dir / filenames[category]

    lines = [json.dumps(s, ensure_ascii=False) for s in samples]
    out_file.write_text("\n".join(lines) + "\n")
    print(f"  Wrote {len(samples)} samples to {out_file.relative_to(DATA_DIR.parent)}")


def print_summary(all_samples: dict[str, list[dict]]):
    """Print dataset assembly summary."""
    print("\n" + "=" * 60)
    print("DATASET ASSEMBLY SUMMARY")
    print("=" * 60)

    total = 0
    for cat, samples in all_samples.items():
        type_counts: Counter = Counter()
        for s in samples:
            for ann in s.get("annotations", []):
                type_counts[ann["entity_type"]] += 1

        print(f"\n{cat.upper()}: {len(samples)} samples")
        for etype, count in type_counts.most_common():
            print(f"  {etype:20s}: {count}")
        total += len(samples)

    print(f"\nTOTAL: {total} samples across {len(all_samples)} categories")


def main():
    parser = argparse.ArgumentParser(description="Assemble benchmark dataset from calibration sources")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE, help="Calibration data directory")
    parser.add_argument("--dry-run", action="store_true", help="Show counts without writing")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)

    if not args.source_dir.exists():
        print(f"Source directory not found: {args.source_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Source: {args.source_dir}")
    print(f"Output: {DATA_DIR}")
    print(f"Seed: {args.seed}")

    all_samples: dict[str, list[dict]] = {}

    # Assemble each category
    all_samples["standard"] = assemble_standard(args.source_dir)
    all_samples["ambiguous"] = assemble_ambiguous(args.source_dir)
    all_samples["contextual"] = assemble_contextual(args.source_dir)
    all_samples["adversarial"] = assemble_adversarial(args.source_dir)

    # Write output
    for cat, samples in all_samples.items():
        write_category(cat, samples, dry_run=args.dry_run)

    print_summary(all_samples)

    # Validate
    if not args.dry_run:
        print("\nRunning validation...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/validate_dataset.py"],
            cwd=DATA_DIR.parent,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            print("[WARNING] Validation found errors — check output above")


if __name__ == "__main__":
    main()
