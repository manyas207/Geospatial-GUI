"""Combine accuracy metrics into a single report."""

from dataclasses import dataclass, field
from typing import Any

from accuracy import metrics, overall_accuracy, precision


@dataclass
class AccuracyReport:
    overall_accuracy: float | None = None
    precision: dict[str, float] = field(default_factory=dict)
    statistics: dict[str, float] = field(default_factory=dict)


def run_accuracy_assessment(
    predictions: Any,
    reference: Any,
) -> AccuracyReport:
    oa = overall_accuracy.compute(predictions, reference)
    prec = precision.compute_per_class(predictions, reference)
    stats = metrics.compute_statistics(predictions, reference)
    return AccuracyReport(overall_accuracy=oa, precision=prec, statistics=stats)
