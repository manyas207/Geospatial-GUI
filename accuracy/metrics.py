"""Additional statistical metrics (recall, F1, kappa, RMSE, etc.)."""

from typing import Any


def compute_statistics(predictions: Any, reference: Any) -> dict[str, float]:
    _ = (predictions, reference)
    return {}
