"""Risk model: probability that a test file is affected by a change.

Without training data the model falls back to a transparent prior whose weights follow the
coefficients learned in the study (changed test > line coverage > file coverage > the rest).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

from .features import FEATURES

PRIOR = {"cov_line": 4.5, "cov_func": 1.0, "cov_file": 3.3, "static_inv_dist": 0.5,
         "name_match": 0.8, "cochange": 0.3, "test_changed": 7.0, "intercept": -5.0}


class RiskModel:
    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = dict(weights or PRIOR)

    def score(self, row: dict) -> float:
        z = self.weights.get("intercept", 0.0) + sum(self.weights.get(k, 0.0) * float(row[k]) for k in FEATURES)
        return 1.0 / (1.0 + math.exp(-z))

    def scores(self, rows: dict[str, dict]) -> dict[str, float]:
        return {t: self.score(r) for t, r in rows.items()}

    @classmethod
    def train(cls, rows: list[dict], labels: list[int]) -> RiskModel:
        if len(set(labels)) < 2:
            return cls()
        X = np.array([[float(r[k]) for k in FEATURES] for r in rows])
        m = LogisticRegression(class_weight="balanced", max_iter=2000).fit(X, np.array(labels))
        w = dict(zip(FEATURES, map(float, m.coef_[0]), strict=True))
        w["intercept"] = float(m.intercept_[0])
        return cls(w)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.weights, indent=1))

    @classmethod
    def load(cls, path: str | Path) -> RiskModel:
        p = Path(path)
        if not p.exists():
            return cls()
        try:
            w = json.loads(p.read_text())
        except (OSError, ValueError) as e:
            raise RuntimeError(f"{p} is not a readable risk model ({e}); delete it to use the built-in prior") from None
        if not isinstance(w, dict) or not w or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in w.values()):
            raise RuntimeError(f"{p} is not a risk model (expected an object of finite feature weights); delete it to "
                               "use the built-in prior")
        return cls({str(k): float(v) for k, v in w.items()})
