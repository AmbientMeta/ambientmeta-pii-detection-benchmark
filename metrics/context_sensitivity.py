"""Context Sensitivity Score (CSS) — novel metric for context-aware PII detection.

CSS measures a system's ability to correctly classify the same surface string
differently based on surrounding context. Computed only on paired contextual samples.

For each context pair (same string, different ground truth types):
- Correct: system gets BOTH right -> +1
- Partially correct: system gets one right -> +0.5
- Incorrect: system gets neither right (or classifies both the same) -> 0
"""

from __future__ import annotations

from dataclasses import dataclass

from adapters.base import DetectedEntity


@dataclass
class CSSResult:
    score: float  # 0.0 - 1.0
    total_pairs: int
    correct: int
    partial: int
    incorrect: int

    def to_dict(self) -> dict:
        return {
            "css": round(self.score, 4),
            "total_pairs": self.total_pairs,
            "correct": self.correct,
            "partial": self.partial,
            "incorrect": self.incorrect,
        }


def _find_detection_for_span(
    detections: list[DetectedEntity],
    target_text: str,
    target_start: int,
    target_end: int,
    iou_threshold: float = 0.3,
) -> DetectedEntity | None:
    """Find the best matching detection for a ground truth span."""
    best: DetectedEntity | None = None
    best_iou = 0.0
    for det in detections:
        inter_start = max(det.start, target_start)
        inter_end = min(det.end, target_end)
        intersection = max(0, inter_end - inter_start)
        union = (det.end - det.start) + (target_end - target_start) - intersection
        iou = intersection / union if union > 0 else 0.0
        if iou >= iou_threshold and iou > best_iou:
            best = det
            best_iou = iou
    return best


def compute_css(
    pairs: list[dict],
    detections_by_id: dict[str, list[DetectedEntity]],
) -> CSSResult:
    """Compute Context Sensitivity Score from paired samples.

    Args:
        pairs: List of pair dicts, each with keys:
            - sample_a: dict with id, annotations (list with start, end, text, entity_type)
            - sample_b: dict with id, annotations
        detections_by_id: Map of sample ID -> list of DetectedEntity from the adapter
    """
    total = 0
    correct = 0
    partial = 0
    incorrect = 0

    for pair in pairs:
        a = pair["sample_a"]
        b = pair["sample_b"]
        a_id = a["id"]
        b_id = b["id"]

        a_dets = detections_by_id.get(a_id, [])
        b_dets = detections_by_id.get(b_id, [])

        a_ann = a["annotations"][0]  # Primary annotation for the ambiguous span
        b_ann = b["annotations"][0]

        # Find what the system detected for the ambiguous span in each context
        a_det = _find_detection_for_span(a_dets, a_ann["text"], a_ann["start"], a_ann["end"])
        b_det = _find_detection_for_span(b_dets, b_ann["text"], b_ann["start"], b_ann["end"])

        a_correct = a_det is not None and a_det.entity_type == a_ann["entity_type"]
        b_correct = b_det is not None and b_det.entity_type == b_ann["entity_type"]

        total += 1
        if a_correct and b_correct:
            correct += 1
        elif a_correct or b_correct:
            partial += 1
        else:
            incorrect += 1

    score = (correct + 0.5 * partial) / total if total > 0 else 0.0
    return CSSResult(
        score=score,
        total_pairs=total,
        correct=correct,
        partial=partial,
        incorrect=incorrect,
    )
