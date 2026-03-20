#!/usr/bin/env python3
"""PII Detection Benchmark — run all adapters against the dataset and produce results."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from adapters.base import PIIDetectorAdapter, DetectedEntity
from adapters.regex_only import RegexOnlyAdapter
from adapters.spacy_ner import SpacyNERAdapter
from adapters.presidio import PresidioAdapter
from adapters.ambientmeta import AmbientMetaAdapter
from metrics.core import compute_span_metrics, GroundTruthSpan, SpanMetrics
from metrics.context_sensitivity import compute_css
from metrics.latency import LatencyTracker

console = Console()

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"
CATEGORIES = ["standard", "ambiguous", "contextual", "adversarial"]

ALL_ADAPTERS: dict[str, type[PIIDetectorAdapter]] = {
    "regex": RegexOnlyAdapter,
    "spacy": SpacyNERAdapter,
    "presidio": PresidioAdapter,
    "ambientmeta": AmbientMetaAdapter,
}


def load_dataset(category: str) -> tuple[list[dict], set[str]]:
    """Load JSONL dataset and scored entity types for a category."""
    jsonl_files = list((DATA_DIR / category).glob("*.jsonl"))
    if not jsonl_files:
        console.print(f"[yellow]Warning: No .jsonl files in data/{category}/[/yellow]")
        return [], set()

    samples = []
    for f in jsonl_files:
        for line in f.read_text().strip().splitlines():
            if line.strip():
                samples.append(json.loads(line))

    # Load scored_entity_types from metadata.json — only these types are
    # annotated in this category. Detections of other types are NOT counted
    # as false positives (the dataset simply doesn't annotate them).
    scored_types: set[str] = set()
    meta_path = DATA_DIR / category / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        scored_types = set(meta.get("scored_entity_types", []))

    return samples, scored_types


def build_context_pairs(samples: list[dict]) -> list[dict]:
    """Build context pairs from samples with context_pair references."""
    by_id = {s["id"]: s for s in samples}
    seen: set[str] = set()
    pairs = []
    for s in samples:
        pair_id = s.get("context_pair")
        if not pair_id or s["id"] in seen:
            continue
        partner = by_id.get(pair_id)
        if partner and partner["id"] not in seen:
            pairs.append({"sample_a": s, "sample_b": partner})
            seen.add(s["id"])
            seen.add(partner["id"])
    return pairs


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def run_adapter_on_category(
    adapter: PIIDetectorAdapter,
    samples: list[dict],
    scored_types: set[str] | None = None,
) -> tuple[SpanMetrics, dict[str, list[DetectedEntity]], LatencyTracker]:
    """Run an adapter on all samples in a category, return metrics + raw detections.

    If scored_types is provided, detections of entity types NOT in the set are
    excluded from metrics (they are not false positives — the dataset simply
    doesn't annotate those types in this category).
    """
    tracker = LatencyTracker()
    all_predictions: list[DetectedEntity] = []
    all_ground_truth: list[GroundTruthSpan] = []
    detections_by_id: dict[str, list[DetectedEntity]] = {}

    # Offset tracking for aggregation across samples
    offset = 0

    tracker.start_session()
    for sample in samples:
        text = sample["text"]
        gt_spans = [
            GroundTruthSpan(
                start=a["start"] + offset,
                end=a["end"] + offset,
                text=a["text"],
                entity_type=a["entity_type"],
            )
            for a in sample.get("annotations", [])
        ]
        all_ground_truth.extend(gt_spans)

        with tracker.time_call():
            detections = adapter.detect(text)

        # Use server-side processing time if available (e.g. AmbientMeta API)
        server_ms = getattr(adapter, "last_processing_ms", None)
        if server_ms is not None:
            tracker._timings[-1] = server_ms

        # Store raw detections by sample ID (original offsets for CSS)
        detections_by_id[sample["id"]] = detections

        # Offset detections for aggregate metrics
        for det in detections:
            all_predictions.append(
                DetectedEntity(
                    start=det.start + offset,
                    end=det.end + offset,
                    text=det.text,
                    entity_type=det.entity_type,
                    confidence=det.confidence,
                )
            )
        offset += len(text) + 1000  # large gap between samples

    tracker.end_session()

    # Filter predictions to only scored entity types — detections of types
    # not annotated in this category are excluded (not false positives).
    if scored_types:
        all_predictions = [p for p in all_predictions if p.entity_type in scored_types]

    metrics = compute_span_metrics(all_predictions, all_ground_truth)
    return metrics, detections_by_id, tracker


def run_benchmark(
    adapter_names: list[str] | None = None,
    category_names: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Run the full benchmark and return results dict."""
    if adapter_names is None:
        adapter_names = list(ALL_ADAPTERS.keys())
    if category_names is None:
        category_names = CATEGORIES
    if output_dir is None:
        output_dir = RESULTS_DIR

    # Filter out AmbientMeta if no API key
    if "ambientmeta" in adapter_names and not os.environ.get("AMBIENTMETA_API_KEY"):
        console.print(
            "[yellow]Skipping AmbientMeta adapter (AMBIENTMETA_API_KEY not set)[/yellow]"
        )
        adapter_names = [a for a in adapter_names if a != "ambientmeta"]

    # Load datasets + scored entity types per category
    datasets: dict[str, list[dict]] = {}
    scored_types_by_cat: dict[str, set[str]] = {}
    for cat in category_names:
        samples, scored_types = load_dataset(cat)
        datasets[cat] = samples
        scored_types_by_cat[cat] = scored_types
        types_note = f" (scoring: {', '.join(sorted(scored_types))})" if scored_types else ""
        console.print(f"Loaded {len(samples)} samples for [bold]{cat}[/bold]{types_note}")

    if not any(datasets.values()):
        console.print("[red]No dataset samples found. Add .jsonl files to data/ directories.[/red]")
        return {}

    # Compute dataset hashes
    dataset_hashes = {}
    for cat in category_names:
        for f in (DATA_DIR / cat).glob("*.jsonl"):
            dataset_hashes[str(f.relative_to(DATA_DIR))] = file_sha256(f)

    results: dict = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "dataset_hashes": dataset_hashes,
        },
        "adapters": {},
    }

    for adapter_name in adapter_names:
        adapter_cls = ALL_ADAPTERS[adapter_name]
        adapter = adapter_cls()

        console.print(f"\n[bold blue]Running: {adapter.name()}[/bold blue]")
        try:
            adapter.setup()
        except Exception as e:
            console.print(f"[red]Setup failed for {adapter.name()}: {e}[/red]")
            continue

        adapter_results: dict = {"name": adapter.name(), "categories": {}, "aggregate": {}}
        all_tp = all_fp = all_fn = 0
        all_per_type: dict[str, SpanMetrics] = {}

        for cat in category_names:
            samples = datasets[cat]
            if not samples:
                continue

            console.print(f"  Category: {cat} ({len(samples)} samples)...", end=" ")
            scored_types = scored_types_by_cat.get(cat)
            metrics, detections_by_id, tracker = run_adapter_on_category(
                adapter, samples, scored_types=scored_types,
            )
            latency = tracker.compute()

            cat_result = {
                "metrics": metrics.to_dict(),
                "latency": latency.to_dict(),
                "sample_count": len(samples),
            }

            # CSS for contextual category
            if cat == "contextual":
                pairs = build_context_pairs(samples)
                if pairs:
                    css_result = compute_css(pairs, detections_by_id)
                    cat_result["css"] = css_result.to_dict()
                    console.print(
                        f"F1={metrics.f1:.3f} CSS={css_result.score:.3f} "
                        f"({latency.p50_ms:.1f}ms p50)"
                    )
                else:
                    console.print(f"F1={metrics.f1:.3f} (no context pairs) ({latency.p50_ms:.1f}ms p50)")
            else:
                console.print(f"F1={metrics.f1:.3f} ({latency.p50_ms:.1f}ms p50)")

            adapter_results["categories"][cat] = cat_result
            all_tp += metrics.tp
            all_fp += metrics.fp
            all_fn += metrics.fn
            for etype, tm in metrics.per_type.items():
                if etype not in all_per_type:
                    all_per_type[etype] = SpanMetrics()
                all_per_type[etype].tp += tm.tp
                all_per_type[etype].fp += tm.fp
                all_per_type[etype].fn += tm.fn

        # Aggregate metrics
        agg = SpanMetrics(tp=all_tp, fp=all_fp, fn=all_fn)
        agg.compute_rates()
        for tm in all_per_type.values():
            tm.compute_rates()
        agg.per_type = {k: v for k, v in all_per_type.items() if v.tp + v.fp + v.fn > 0}
        adapter_results["aggregate"] = agg.to_dict()

        adapter.teardown()
        results["adapters"][adapter_name] = adapter_results

    # Print summary table
    _print_summary(results)

    # Write results
    output_dir.mkdir(parents=True, exist_ok=True)
    latest = output_dir / "latest.json"
    latest.write_text(json.dumps(results, indent=2))
    console.print(f"\nResults written to [bold]{latest}[/bold]")

    # Historical snapshot
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    hist_dir = output_dir / "historical"
    hist_dir.mkdir(exist_ok=True)
    (hist_dir / f"results_{ts}.json").write_text(json.dumps(results, indent=2))

    return results


def _print_summary(results: dict) -> None:
    """Print a Rich summary table to the console."""
    if not results.get("adapters"):
        return

    table = Table(title="PII Detection Benchmark Results")
    table.add_column("System", style="bold")
    table.add_column("Overall F1", justify="right")

    for cat in CATEGORIES:
        table.add_column(f"{cat.title()} F1", justify="right")

    table.add_column("CSS", justify="right", style="bold cyan")

    for adapter_data in results["adapters"].values():
        row = [adapter_data["name"]]
        agg = adapter_data.get("aggregate", {})
        row.append(f"{agg.get('f1', 0):.1%}")

        for cat in CATEGORIES:
            cat_data = adapter_data.get("categories", {}).get(cat, {})
            cat_metrics = cat_data.get("metrics", {})
            row.append(f"{cat_metrics.get('f1', 0):.1%}")

        # CSS
        ctx = adapter_data.get("categories", {}).get("contextual", {})
        css = ctx.get("css", {})
        css_val = css.get("css", 0)
        row.append(f"{css_val:.1%}" if css else "N/A")

        table.add_row(*row)

    console.print()
    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="Run the PII Detection Benchmark")
    parser.add_argument(
        "--adapter",
        choices=list(ALL_ADAPTERS.keys()),
        nargs="+",
        help="Run specific adapter(s) only",
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        nargs="+",
        help="Run specific category(ies) only",
    )
    parser.add_argument("--output", type=Path, help="Output directory for results")
    args = parser.parse_args()

    run_benchmark(
        adapter_names=args.adapter,
        category_names=args.category,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
