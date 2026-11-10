"""Residual risk r(c) of a selection: 1 - prod over skipped tests of (1 - p~(i))."""
from __future__ import annotations

from sklearn.isotonic import IsotonicRegression


class Recalibrator:
    """Isotonic map from model scores to observed frequencies of affected tests."""

    def __init__(self):
        self.iso = None

    def fit(self, scores: list[float], labels: list[int]) -> Recalibrator:
        if len(set(labels)) >= 2:
            self.iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(scores, labels)
        return self

    def __call__(self, p: float) -> float:
        return float(self.iso.predict([p])[0]) if self.iso is not None else p


def residual_risk(scores: dict[str, float], selected: set[str], recal=lambda p: p) -> float:
    keep = 1.0
    for t, p in scores.items():
        if t not in selected:
            keep *= 1.0 - recal(p)
    return 1.0 - keep
