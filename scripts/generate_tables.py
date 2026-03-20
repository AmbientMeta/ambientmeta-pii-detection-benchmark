#!/usr/bin/env python3
"""Generate markdown tables from benchmark results JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def generate_summary_table(results: dict) -> str:
    """Generate the main comparison table."""
    lines = [
        "| System | Overall F1 | Standard F1 | Ambiguous F1 | CSS | Adversarial F1 |",
        "|--------|-----------|-------------|--------------|-----|----------------|",
    ]

    for adapter_data in results.get("adapters", {}).values():
        name = adapter_data["name"]
        agg = adapter_data.get("aggregate", {})
        overall_f1 = f"{agg.get('f1', 0):.1%}"

        cats = adapter_data.get("categories", {})
        std_f1 = f"{cats.get('standard', {}).get('metrics', {}).get('f1', 0):.1%}"
        amb_f1 = f"{cats.get('ambiguous', {}).get('metrics', {}).get('f1', 0):.1%}"
        adv_f1 = f"{cats.get('adversarial', {}).get('metrics', {}).get('f1', 0):.1%}"

        ctx = cats.get("contextual", {})
        css = ctx.get("css", {}).get("css", None)
        css_str = f"{css:.1%}" if css is not None else "N/A"

        # Bold the best
        lines.append(f"| {name} | {overall_f1} | {std_f1} | {amb_f1} | {css_str} | {adv_f1} |")

    return "\n".join(lines)


def generate_per_entity_table(results: dict) -> str:
    """Generate per-entity-type breakdown."""
    # Collect all entity types across all adapters
    all_types: set[str] = set()
    for adapter_data in results.get("adapters", {}).values():
        agg = adapter_data.get("aggregate", {})
        per_type = agg.get("per_type", {})
        all_types.update(per_type.keys())

    if not all_types:
        return "*No per-entity data available.*"

    sorted_types = sorted(all_types)
    adapter_names = [a["name"] for a in results.get("adapters", {}).values()]

    header = "| Entity Type | " + " | ".join(adapter_names) + " |"
    sep = "|-------------|" + "|".join(["------" for _ in adapter_names]) + "|"
    lines = [header, sep]

    for etype in sorted_types:
        row = [etype]
        for adapter_data in results.get("adapters", {}).values():
            per_type = adapter_data.get("aggregate", {}).get("per_type", {})
            type_data = per_type.get(etype, {})
            f1 = type_data.get("f1", None)
            row.append(f"{f1:.1%}" if f1 is not None else "—")
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def generate_latency_table(results: dict) -> str:
    """Generate latency comparison table."""
    lines = [
        "| System | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (docs/s) |",
        "|--------|---------|---------|---------|-------------------|",
    ]

    for adapter_data in results.get("adapters", {}).values():
        name = adapter_data["name"]
        # Aggregate latency from all categories
        all_p50 = []
        all_p95 = []
        all_p99 = []
        total_docs = 0
        total_secs = 0.0

        for cat_data in adapter_data.get("categories", {}).values():
            lat = cat_data.get("latency", {})
            if lat.get("total_docs", 0) > 0:
                all_p50.append(lat.get("p50_ms", 0))
                all_p95.append(lat.get("p95_ms", 0))
                all_p99.append(lat.get("p99_ms", 0))
                total_docs += lat.get("total_docs", 0)
                total_secs += lat.get("total_seconds", 0)

        if all_p50:
            p50 = sum(all_p50) / len(all_p50)
            p95 = sum(all_p95) / len(all_p95)
            p99 = sum(all_p99) / len(all_p99)
            tps = total_docs / total_secs if total_secs > 0 else 0
            lines.append(f"| {name} | {p50:.1f} | {p95:.1f} | {p99:.1f} | {tps:.1f} |")
        else:
            lines.append(f"| {name} | — | — | — | — |")

    return "\n".join(lines)


def main():
    results_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/latest.json")
    if not results_path.exists():
        print(f"Results file not found: {results_path}", file=sys.stderr)
        sys.exit(1)

    results = json.loads(results_path.read_text())

    print("## Quick Results\n")
    print(generate_summary_table(results))
    print("\n## Per-Entity Results\n")
    print(generate_per_entity_table(results))
    print("\n## Latency\n")
    print(generate_latency_table(results))


if __name__ == "__main__":
    main()
