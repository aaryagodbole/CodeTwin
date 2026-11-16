"""CT001: the calibrated selection abstained because the residual risk is above the target."""
from __future__ import annotations

from ..context import ReviewContext
from ..model import Finding, Severity

NAME = "residual_risk"
DEFAULT = True


def analyze(ctx: ReviewContext) -> list[Finding]:
    d = ctx.decision
    if d.get("decision") != "abstain":
        return []
    alpha = ctx.section("change_risk").get("alpha", getattr(ctx.cfg, "alpha", None))
    target = f" (target {alpha:.0%})" if isinstance(alpha, (int, float)) else ""
    return [Finding(
        rule="CT001", severity=Severity.HIGH,
        title=f"CodeTwin abstained: skipping tests is not safe enough{target}",
        message="CodeTwin could not select a subset of tests that keeps the estimated chance of missing an "
                "affected test within the target, so it fell back to a broader selection. The reasons below give "
                "the estimate. Run the broader selection before merging.",
        evidence=[str(r) for r in d.get("reasons", [])],
        suggestion="Run the full test suite (or file-level coverage selection) for this pull request.")]
