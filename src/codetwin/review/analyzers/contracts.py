"""CT004: breaking OpenAPI / JSON-schema changes, with the code sites and tests that may rely on them.

Reads the `contracts` report section (src/codetwin/contracts/link.py).
"""
from __future__ import annotations

from ..context import ReviewContext
from ..model import Finding, Severity

NAME = "contracts"
DEFAULT = True
_MAX_SITES = 10


def analyze(ctx: ReviewContext) -> list[Finding]:
    out: list[Finding] = []
    for b in ctx.section("contracts").get("breaking", []):
        consumers = b.get("consumers", [])
        sites = [f"{c.get('repo', '')}:{c.get('file')}:{c.get('line')} ({c.get('how', 'uses')})" for c in consumers]
        tests = sorted(b.get("tests", {}))
        out.append(Finding(
            rule="CT004", severity=Severity.HIGH if consumers else Severity.MEDIUM,
            title=f"Breaking contract change ({b.get('kind', 'changed')}): {b.get('location')}",
            message=f"{b.get('detail', 'A breaking change')} in `{b.get('file')}`. "
                    + (f"{len(consumers)} code sites use it." if consumers else
                       "No code using it was found, but clients outside the connected repositories may."),
            path=b.get("file"),
            evidence=sites[:_MAX_SITES] + ([f"... and {len(sites) - _MAX_SITES} more"] if len(sites) > _MAX_SITES else [])
            + ([f"tests that reach a consumer: {', '.join(tests[:5])}"] if tests else []),
            suggestion="Version the API or keep the old field/operation, and run the consumers' tests."))
    return out
