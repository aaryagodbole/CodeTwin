"""Layer 3: choosing tests and deciding whether to proceed or abstain (Algorithm 1 of the paper)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .risk.residual import residual_risk

OUTPUT_SCHEMA = 1   # bump only for breaking changes to Decision.to_dict(); adding extras is not breaking


@dataclass
class Decision:
    selected: set[str]
    decision: str                       # "proceed" | "abstain"
    residual_risk: float
    threshold: float | None = None
    mode: str = "calibrated"
    reasons: list[str] = field(default_factory=list)
    extras: dict = field(default_factory=dict)      # report sections (codetwin/report/), by name
    # Estimated residual risk of the first selection. residual_risk is always the risk of `selected`, the tests
    # that run; the two differ when the decision abstains to a broader selection or to every test.
    risk_before: float | None = None

    def to_dict(self) -> dict:
        """The output contract of `select --json`, MCP and the VS Code extension (docs/output.md)."""
        before = None if self.risk_before is None else round(self.risk_before, 4)
        return {"schema": OUTPUT_SCHEMA, "decision": self.decision, "residual_risk": round(self.residual_risk, 4),
                "risk_before": before, "threshold": self.threshold, "mode": self.mode, "selected": sorted(self.selected),
                "reasons": self.reasons, "extras": self.extras}


def budget_select(rows: dict[str, dict], scores: dict[str, float], times: dict[str, float], budget_s: float) -> set[str]:
    """Forced tests first, then the most risk per second while the budget allows."""
    sel, used = set(), 0.0
    for t, r in rows.items():
        if r["forced"]:
            sel.add(t)
            used += times.get(t, 0.0)
    for t in sorted(rows, key=lambda t: (-scores[t] / max(times.get(t, 1e-3), 1e-3), t)):
        if t not in sel and used + times.get(t, 0.0) <= budget_s:
            sel.add(t)
            used += times.get(t, 0.0)
    return sel


def threshold_select(rows: dict[str, dict], scores: dict[str, float], lam: float) -> set[str]:
    if lam < 0:
        return set(rows)
    return {t for t, r in rows.items() if r["forced"] or scores[t] >= lam}


def decide(rows, scores, selected, alpha, recal=lambda p: p, fallback: str = "file-coverage", mode="calibrated",
           threshold=None) -> Decision:
    """Abstain to a broader run when the estimated residual risk exceeds the target."""
    r = residual_risk(scores, selected, recal)
    if r <= alpha:
        return Decision(selected, "proceed", r, threshold, mode, [f"estimated residual risk {r:.1%} <= target {alpha:.0%}"],
                        risk_before=r)
    broader = set(rows) if fallback == "full" else selected | {t for t, row in rows.items() if row["cov_file"]}
    r2 = residual_risk(scores, broader, recal)
    return Decision(broader, "abstain", r2, threshold, mode,
                    [f"estimated residual risk {r:.1%} > target {alpha:.0%}; running the broader {fallback} selection "
                     f"(estimated residual risk {r2:.1%})"], risk_before=r)
