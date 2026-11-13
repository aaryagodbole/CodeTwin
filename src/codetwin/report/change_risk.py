"""Section: calibrated change-level risk q(c) of the selection, next to the product formula r(c).

Advisory for now: the proceed/abstain decision still uses r(c) (selection.py, fixed by the paper).
When the paper adopts q(c) for abstention, the decision moves to selection.py.
"""
from __future__ import annotations

from ..risk.change_risk import ChangeRiskModel, features, triggers
from ..risk.residual import Recalibrator

NAME = "change_risk"


def contribute(ctx) -> dict:
    d = ctx.decision
    if not ctx.rows:
        return {"summary": "no tests"}
    pts = ctx.store.get_state("recal_points", [])
    recal = Recalibrator().fit([p[0] for p in pts], [p[1] for p in pts])
    now = ctx.facts_now() if ctx.facts_now else {}
    trig = triggers(ctx.diff, ctx.prev, ctx.store.get_static(ctx.base), now, ctx.is_source)
    z = features(ctx.rows, ctx.scores, set(d.selected), recal, trig)
    model = ChangeRiskModel.fit(ctx.store.get_state("change_points", []))
    q = model(z)
    ctx.store.set_state("pending_change_features", z)    # labelled by `codetwin learn` (commands/learn.py)
    alpha = ctx.cfg.alpha
    return {"q": round(q, 4), "r_product": round(z["r_prod"], 4), "alpha": alpha, "model": model.source,
            "features": {k: round(v, 4) for k, v in z.items()}, "triggers": trig,
            "above_target": q > alpha,
            "summary": f"calibrated change-level risk {q:.1%} (product formula {z['r_prod']:.1%}); "
                       f"{'above' if q > alpha else 'within'} target {alpha:.0%}"}
