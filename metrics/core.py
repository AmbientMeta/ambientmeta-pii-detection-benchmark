"""Span-level precision, recall, F1 with IoU matching."""

from __future__ import annotations

from dataclasses import dataclass, field

from adapters.base import DetectedEntity


@dataclass
class GroundTruthSpan:
    start: int
    end: int
    text: str
    entity_type: str


@dataclass
class SpanMetrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    per_type: dict[str, "SpanMetrics"] = field(default_factory=dict)

    def compute_rates(self) -> None:
        self.precision = self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0
        self.recall = self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0
        self.f1 = (
            2 * self.precision * self.recall / (self.precision + self.recall)
            if (self.precision + self.recall) > 0
            else 0.0
        )

    def to_dict(self) -> dict:
        d = {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }
        if self.per_type:
            d["per_type"] = {k: v.to_dict() for k, v in self.per_type.items()}
        return d


def _iou(pred_start: int, pred_end: int, gt_start: int, gt_end: int) -> float:
    """Intersection over Union for two character spans."""
    inter_start = max(pred_start, gt_start)
    inter_end = min(pred_end, gt_end)
    intersection = max(0, inter_end - inter_start)
    union = (pred_end - pred_start) + (gt_end - gt_start) - intersection
    return intersection / union if union > 0 else 0.0


def compute_span_metrics(
    predictions: list[DetectedEntity],
    ground_truth: list[GroundTruthSpan],
    iou_threshold: float = 0.5,
) -> SpanMetrics:
    """Compute span-level metrics with IoU matching and entity type checking.

    A prediction is a true positive if:
    1. It overlaps a ground truth span with IoU >= threshold
    2. The predicted entity type matches the ground truth entity type

    Each ground truth span can match at most one prediction (greedy, best IoU first).
    """
    metrics = SpanMetrics()
    all_types: set[str] = set()

    for gt in ground_truth:
        all_types.add(gt.entity_type)
    for pred in predictions:
        all_types.add(pred.entity_type)

    type_metrics: dict[str, SpanMetrics] = {t: SpanMetrics() for t in all_types}

    # Build match candidates sorted by IoU descending
    matches: list[tuple[float, int, int]] = []  # (iou, pred_idx, gt_idx)
    for pi, pred in enumerate(predictions):
        for gi, gt in enumerate(ground_truth):
            score = _iou(pred.start, pred.end, gt.start, gt.end)
            if score >= iou_threshold:
                matches.append((score, pi, gi))

    matches.sort(key=lambda x: x[0], reverse=True)

    matched_preds: set[int] = set()
    matched_gts: set[int] = set()

    for _iou_score, pi, gi in matches:
        if pi in matched_preds or gi in matched_gts:
            continue
        pred = predictions[pi]
        gt = ground_truth[gi]
        if pred.entity_type == gt.entity_type:
            # True positive
            metrics.tp += 1
            type_metrics[gt.entity_type].tp += 1
            matched_preds.add(pi)
            matched_gts.add(gi)

    # False positives: predictions that didn't match any ground truth
    for pi, pred in enumerate(predictions):
        if pi not in matched_preds:
            metrics.fp += 1
            type_metrics[pred.entity_type].fp += 1

    # False negatives: ground truth spans that weren't matched
    for gi, gt in enumerate(ground_truth):
        if gi not in matched_gts:
            metrics.fn += 1
            type_metrics[gt.entity_type].fn += 1

    metrics.compute_rates()
    for tm in type_metrics.values():
        tm.compute_rates()

    # Only include types that actually appeared
    metrics.per_type = {k: v for k, v in type_metrics.items() if v.tp + v.fp + v.fn > 0}
    return metrics
