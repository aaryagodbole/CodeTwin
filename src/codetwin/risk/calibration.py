"""Conformal risk control with adaptive conformal inference (Section IV-E of the paper)."""
from __future__ import annotations

import math


def crc_threshold(min_affected_scores: list[float], alpha: float) -> float:
    """Largest lambda with n/(n+1) * R_n(lambda) + 1/(n+1) <= alpha.

    `min_affected_scores` holds, for each calibration change, the smallest score of an affected
    (non-forced) test (math.inf if it had none). Returns -1 if no threshold qualifies (select all)."""
    n = len(min_affected_scores)
    if n == 0:
        return -1.0
    cands = sorted({0.0, 1.0, *[m for m in min_affected_scores if m != math.inf]})
    best = -1.0
    for lam in cands:
        risk = sum(1 for m in min_affected_scores if lam > m) / n
        if n / (n + 1) * risk + 1 / (n + 1) <= alpha:
            best = max(best, lam)
    return best


class AdaptiveLevel:
    """alpha_{t+1} = alpha_t + gamma * (alpha - err_t)  (Gibbs and Candes, 2021)."""

    def __init__(self, alpha: float, gamma: float = 0.02, alpha_t: float | None = None):
        self.alpha, self.gamma = alpha, gamma
        self.alpha_t = alpha if alpha_t is None else alpha_t

    def update(self, missed: bool) -> float:
        self.alpha_t = self.alpha_t + self.gamma * (self.alpha - (1.0 if missed else 0.0))
        return self.alpha_t

    @property
    def level(self) -> float:
        return min(max(self.alpha_t, 0.0), 1.0)
