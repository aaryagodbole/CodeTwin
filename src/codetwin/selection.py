"""The Selection policy: from risk scores to a finished Decision (Algorithm 1 of the paper).

`choose()` is the one place a decision is made. It is pure: it reads feature rows, scores, the calibration
state and what the change says about its evidence, and returns the Decision with every reason. The engine computes
the inputs and stores the result; nothing changes a Decision after `choose()` returns it.

Paper semantics kept here: abstain to a broader run when the estimated residual risk exceeds alpha; a conformal
threshold of -1 selects every test; before the calibration set can reach the adaptive level, a fixed threshold is
used and the decision says so; a changed file whose tests have no runtime evidence runs every test.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .risk.residual import residual_risk

if TYPE_CHECKING:
    from .risk.ledger import CalibrationState

UNCALIBRATED_THRESHOLD = 0.5    # used until the calibration set is large enough for the adaptive level

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


def only_tests(rows: dict[str, dict], notes: Iterable[str] = ()) -> Decision:
    """A change that edits no source file: run the added and changed tests, nothing is at risk."""
    return Decision({t for t, r in rows.items() if r["forced"]}, "proceed", 0.0, None, "no-source-change",
                    ["no source file changed; only added or changed tests run", *notes], risk_before=0.0)


def choose(rows: dict[str, dict], scores: dict[str, float], state: CalibrationState, *, alpha: float,
           fallback: str = "file-coverage", budget: float | None = None, times: dict[str, float] | None = None,
           blind: dict[str, str] | None = None, notes: Iterable[str] = ()) -> Decision:
    """The decision for a change that edits source files.

    `budget` (a share of the full suite's time, with `times` per test) selects by risk per second; otherwise the
    conformal threshold of `state` selects. `blind` maps changed files whose tests have no runtime evidence to the
    reason: then every test runs. `notes` are reasons that weaken the evidence (unknowns, thin history)."""
    recal = state.recalibrator
    if budget is not None:
        times = times or {}
        sel = budget_select(rows, scores, times, budget * sum(times.values()))
        d = decide(rows, scores, sel, alpha, recal, fallback, mode=f"budget {budget:.0%}")
        risk_at = 0                                    # position of decide()'s risk sentence in d.reasons
    else:
        lam = state.threshold
        first: list[str] = []
        if lam is None:
            lam = UNCALIBRATED_THRESHOLD
            first = [f"not calibrated yet ({len(state.calibration)} labelled changes); using threshold {lam}"]
        d = decide(rows, scores, threshold_select(rows, scores, lam), alpha, recal, fallback, threshold=lam)
        risk_at = len(first)
        d.reasons = first + d.reasons
    d.reasons += list(notes)
    if blind:
        # Unknown is not "no dependency": without coverage for these files' tests, the risk of skipping a test
        # cannot be estimated. Run everything and say why.
        d.decision, d.selected = "abstain", set(rows)
        d.residual_risk = residual_risk(scores, d.selected, recal)   # the risk of what now runs (E2)
        # decide()'s sentence describes a selection that does not run: keep it and add the risk of what runs.
        d.reasons[risk_at] += f"; running every test instead (estimated residual risk {d.residual_risk:.1%})"
        for why in sorted(set(blind.values())):
            fs = sorted(f for f, w in blind.items() if w == why)
            d.reasons.append(f"{why} for {', '.join(fs[:5])}{' and others' if len(fs) > 5 else ''}: "
                             "static evidence only, running every test (see docs/languages.md)")
    return d
