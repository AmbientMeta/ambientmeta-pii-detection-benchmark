#!/usr/bin/env python3
"""Validate dataset files against the benchmark schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console

console = Console()

DATA_DIR = Path(__file__).parent.parent / "data"

REQUIRED_FIELDS = {"id", "text", "annotations"}
REQUIRED_ANNOTATION_FIELDS = {"start", "end", "text", "entity_type"}
VALID_ENTITY_TYPES = {
    "PERSON", "EMAIL", "PHONE", "SSN", "CREDIT_CARD", "LOCATION",
    "NPI", "MRN", "ORGANIZATION", "ADDRESS", "DOB", "IP_ADDRESS",
    "URL", "CREDENTIALS", "DEA", "BANK_ROUTING_NUMBER", "REFERENCE_ID",
}
VALID_CATEGORIES = {"standard", "ambiguous", "contextual", "adversarial"}
VALID_DIFFICULTIES = {"standard", "ambiguous", "contextual", "adversarial"}


def validate_sample(sample: dict, line_num: int, filepath: Path) -> list[str]:
    errors: list[str] = []
    loc = f"{filepath.name}:{line_num}"

    # Required fields
    for field in REQUIRED_FIELDS:
        if field not in sample:
            errors.append(f"{loc} — missing required field '{field}'")

    if "id" in sample and not isinstance(sample["id"], str):
        errors.append(f"{loc} — 'id' must be a string")

    if "text" in sample and not isinstance(sample["text"], str):
        errors.append(f"{loc} — 'text' must be a string")

    text = sample.get("text", "")

    # Annotations
    annotations = sample.get("annotations", [])
    if not isinstance(annotations, list):
        errors.append(f"{loc} — 'annotations' must be a list")
        return errors

    for i, ann in enumerate(annotations):
        ann_loc = f"{loc} annotation[{i}]"
        for field in REQUIRED_ANNOTATION_FIELDS:
            if field not in ann:
                errors.append(f"{ann_loc} — missing '{field}'")

        if "entity_type" in ann and ann["entity_type"] not in VALID_ENTITY_TYPES:
            errors.append(f"{ann_loc} — unknown entity_type '{ann['entity_type']}'")

        # Validate span offsets
        start = ann.get("start", 0)
        end = ann.get("end", 0)
        if isinstance(start, int) and isinstance(end, int):
            if start < 0 or end < 0:
                errors.append(f"{ann_loc} — negative offset")
            if start >= end:
                errors.append(f"{ann_loc} — start ({start}) >= end ({end})")
            if end > len(text):
                errors.append(f"{ann_loc} — end ({end}) exceeds text length ({len(text)})")
            elif "text" in ann:
                actual = text[start:end]
                if actual != ann["text"]:
                    errors.append(
                        f"{ann_loc} — span text mismatch: "
                        f"text[{start}:{end}]='{actual}' != annotation text='{ann['text']}'"
                    )

    # Metadata validation
    meta = sample.get("metadata", {})
    if meta:
        cat = meta.get("category")
        if cat and cat not in VALID_CATEGORIES:
            errors.append(f"{loc} — unknown category '{cat}'")

    return errors


def validate_category(category: str) -> tuple[int, int, list[str]]:
    """Validate all JSONL files in a category directory."""
    cat_dir = DATA_DIR / category
    if not cat_dir.exists():
        return 0, 0, [f"Directory data/{category}/ does not exist"]

    jsonl_files = list(cat_dir.glob("*.jsonl"))
    if not jsonl_files:
        return 0, 0, [f"No .jsonl files in data/{category}/"]

    total_samples = 0
    all_errors: list[str] = []
    ids_seen: set[str] = set()

    for filepath in jsonl_files:
        for line_num, line in enumerate(filepath.read_text().strip().splitlines(), 1):
            if not line.strip():
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError as e:
                all_errors.append(f"{filepath.name}:{line_num} — invalid JSON: {e}")
                continue

            total_samples += 1
            errors = validate_sample(sample, line_num, filepath)
            all_errors.extend(errors)

            # Check for duplicate IDs
            sample_id = sample.get("id", "")
            if sample_id in ids_seen:
                all_errors.append(f"{filepath.name}:{line_num} — duplicate id '{sample_id}'")
            ids_seen.add(sample_id)

    return total_samples, len(all_errors), all_errors


def main():
    categories = sys.argv[1:] if len(sys.argv) > 1 else list(VALID_CATEGORIES)

    total_errors = 0
    total_samples = 0

    for cat in categories:
        samples, errors, error_list = validate_category(cat)
        total_samples += samples
        total_errors += errors

        status = "[green]PASS[/green]" if errors == 0 else "[red]FAIL[/red]"
        console.print(f"  {status} {cat}: {samples} samples, {errors} errors")

        for err in error_list[:10]:  # Cap output
            console.print(f"    [red]{err}[/red]")
        if len(error_list) > 10:
            console.print(f"    ... and {len(error_list) - 10} more errors")

    console.print(f"\nTotal: {total_samples} samples, {total_errors} errors")
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
