"""Residual risk r(c) of a selection: 1 - prod over skipped tests of (1 - p~(i))."""
from __future__ import annotations

from sklearn.isotonic import IsotonicRegression


class Recalibrator:
    """Isotonic map from model scores to observed frequencies of affected tests.

    Fitted only with at least MIN_EACH affected and MIN_EACH unaffected examples: an isotonic fit on a handful of
    points is a step function that is very sure of itself (0 or 1 over wide score ranges). Until then the model's
    scores are used as they are, and `select` says so.
    """

    MIN_EACH = 5

    def __init__(self):
        self.iso = None

    @classmethod
    def enough(cls, labels: list[int]) -> bool:
        pos = sum(1 for x in labels if x)
        return pos >= cls.MIN_EACH and len(labels) - pos >= cls.MIN_EACH

    def fit(self, scores: list[float], labels: list[int]) -> Recalibrator:
        if self.enough(labels):
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
