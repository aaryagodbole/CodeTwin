"""Section: is the promised miss rate being kept? (risk promise monitor)

Uses the labelled calibrated decisions in the store (outcomes from `codetwin learn`). Raises an alert
when even the lower end of a 95% Wilson interval of the recent miss rate is above the target.
"""
from __future__ import annotations

import math

NAME = "promise"
WINDOW = 50


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def contribute(ctx) -> dict:
    rows = ctx.store.con.execute(
        "select o.missed from decisions d join outcomes o on o.decision_id = d.id "
        "where d.mode = 'calibrated' order by d.id").fetchall()
    alpha = ctx.cfg.alpha
    recent = [int(r[0]) for r in rows[-WINDOW:]]
    n, k = len(recent), sum(recent)
    lo, hi = wilson(k, n)
    alert = n > 0 and lo > alpha
    if n == 0:
        text = "no labelled changes yet; run `codetwin learn` after full runs"
    else:
        text = (f"observed miss rate {k / n:.1%} over the last {n} labelled changes (95% CI {lo:.0%}-{hi:.0%}), "
                f"target {alpha:.0%}" + ("; ALERT: promise broken, recalibrating" if alert else ""))
    return {"labelled": len(rows), "window": n, "misses": k, "observed": (k / n) if n else None,
            "ci95": [round(lo, 4), round(hi, 4)], "alpha": alpha, "alert": alert, "summary": text}
