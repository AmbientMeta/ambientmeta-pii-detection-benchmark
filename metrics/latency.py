"""Latency tracking — p50, p95, p99, throughput."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class LatencyStats:
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    mean_ms: float = 0.0
    total_docs: int = 0
    total_seconds: float = 0.0
    throughput_docs_per_sec: float = 0.0

    def to_dict(self) -> dict:
        return {
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "total_docs": self.total_docs,
            "total_seconds": round(self.total_seconds, 2),
            "throughput_docs_per_sec": round(self.throughput_docs_per_sec, 2),
        }


class LatencyTracker:
    """Tracks per-document detection latency."""

    def __init__(self):
        self._timings: list[float] = []  # milliseconds
        self._start: float = 0.0
        self._total_elapsed: float = 0.0

    def start_session(self) -> None:
        self._start = time.perf_counter()

    def end_session(self) -> None:
        self._total_elapsed = time.perf_counter() - self._start

    def record(self, duration_ms: float) -> None:
        self._timings.append(duration_ms)

    def time_call(self):
        """Context manager that records the duration of a detection call."""
        return _TimedCall(self)

    def compute(self) -> LatencyStats:
        if not self._timings:
            return LatencyStats()
        arr = np.array(self._timings)
        total_sec = self._total_elapsed if self._total_elapsed > 0 else arr.sum() / 1000
        return LatencyStats(
            p50_ms=float(np.percentile(arr, 50)),
            p95_ms=float(np.percentile(arr, 95)),
            p99_ms=float(np.percentile(arr, 99)),
            mean_ms=float(np.mean(arr)),
            total_docs=len(self._timings),
            total_seconds=total_sec,
            throughput_docs_per_sec=len(self._timings) / total_sec if total_sec > 0 else 0,
        )


class _TimedCall:
    def __init__(self, tracker: LatencyTracker):
        self._tracker = tracker
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._tracker.record(elapsed_ms)
