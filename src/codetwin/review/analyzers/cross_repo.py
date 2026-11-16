"""CT005: connected repositories ([[repos]] in .codetwin.toml) with code that uses a changed symbol.

Reads the `cross_repo` report section (src/codetwin/crossrepo/analysis.py). Only consumers that use a changed
symbol become findings; files that merely import the package are listed as evidence.
"""
from __future__ import annotations

from ...crossrepo.analysis import USES_SYMBOL
from ..context import ReviewContext
from ..model import Finding, Severity

NAME = "cross_repo"
DEFAULT = True


def analyze(ctx: ReviewContext) -> list[Finding]:
    out: list[Finding] = []
    for r in ctx.section("cross_repo").get("repos", []):
        strong = [c for c in r.get("consumers", []) if c.get("link") == USES_SYMBOL]
        if not strong and not r.get("unknowns"):
            continue
        tests = sorted(r.get("tests", {}))
        evidence = [f"{r.get('name')}:{c.get('file')} uses {', '.join(c.get('symbols', []) or [])}".rstrip()
                    for c in strong[:10]] + [str(u) for u in r.get("unknowns", [])[:5]]
        if not strong:
            out.append(Finding(
                rule="CT005", severity=Severity.LOW,
                title=f"Could not tell whether `{r.get('name')}` uses code changed here",
                message=f"CodeTwin could not resolve some links into `{r.get('name')}`, so it cannot say whether that "
                        "repository uses the changed code or whether its tests cover it.",
                evidence=evidence,
                suggestion=f"Check `{r.get('name')}` by hand, or run its test suite before releasing."))
            continue
        out.append(Finding(
            rule="CT005", severity=Severity.MEDIUM,
            title=f"Repository `{r.get('name')}` uses code changed here",
            message=f"{len(strong)} files in `{r.get('name')}` use a symbol this pull request changes"
                    + (f"; {len(tests)} of its tests reach them." if tests else "; none of its tests reach them."),
            evidence=evidence,
            suggestion=f"Run these tests in `{r.get('name')}`: {', '.join(tests[:5])}" if tests else
                       f"Add a test in `{r.get('name')}` for the changed behaviour."))
    return out
