"""Read models: every number the dashboard shows, defined once.

The local API (`codetwin serve`) serialises these; `codetwin push` takes its numbers from here too, so the cloud
shows the same values as the local API for the same project. A view is a plain dict with JSON-safe values: NaN
becomes None and list fields are never null.
"""
from __future__ import annotations

import math
from typing import Any

DECISION_KEYS = ["id", "recorded", "base", "mode", "alpha", "alpha_t", "threshold", "residual_risk", "decision",
                 "selected", "reasons", "missed"]

_NAN_KEYS = ("threshold", "residual_risk", "alpha", "alpha_t")


def _finite(x: Any) -> Any:
    return None if isinstance(x, float) and math.isnan(x) else x


def decision_row(d: dict) -> dict:
    """One decision as the decisions list shows it."""
    out = {k: d.get(k) for k in DECISION_KEYS}
    for k in _NAN_KEYS:
        out[k] = _finite(out.get(k))
    # The keys are always present (from DECISION_KEYS), so a missing list is None here: default it explicitly.
    out["selected"] = out.get("selected") or []
    out["reasons"] = out.get("reasons") or []
    return out


def decision_detail(store: Any, decision_id: int) -> dict | None:
    """One decision with its per-test risk scores, or None when there is no such decision."""
    d = store.decision(decision_id, extras=False)      # the API does not return the sections (yet)
    if d is None:
        return None
    return {**decision_row(d), "scores": {k: _finite(s) for k, s in store.scores(decision_id).items()}}


def run_numbers(run: Any) -> dict:
    """What the dashboard shows about a recorded run: how many test files it ran and its wall time."""
    return {"test_files": len(run.durations) if run else 0, "suite_seconds": run.wall if run else None}


def summary(eng: Any) -> dict:
    """The overview: target and adaptive level, the newest complete recorded run, and decision counts."""
    ch = eng.change(require_run=False)
    run = ch.prev
    return {"root": str(eng.root), "packages": eng.cfg.packages, "alpha": eng.cfg.alpha,
            "alpha_t": eng.ledger.alpha_t(), "calibration_size": eng.ledger.size(),
            "recorded_commit": ch.base if run is not None else None, **run_numbers(run), **eng.store.counts()}


def calibration(store: Any) -> dict:
    """Observed miss rate of labelled calibrated decisions over time, against the target and the level."""
    rows = store.labelled("calibrated")
    points, misses = [], 0
    for i, (did, alpha, alpha_t, missed) in enumerate(rows, 1):
        misses += missed
        points.append({"n": i, "decision_id": did, "alpha": alpha, "alpha_t": alpha_t, "observed_miss_rate": misses / i})
    return {"points": points, "labelled": len(rows), "misses": misses}
