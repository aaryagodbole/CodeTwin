"""CT002: changed functions, methods and classes that no test executed before the change.

Reads the `changed_symbols` report section. A symbol with `tests_before == 0` has no runtime evidence, so no
selection can catch a regression in it; the only fix is a new test.
"""
from __future__ import annotations

from ..context import ReviewContext
from ..model import Finding, Severity

NAME = "untested_change"
DEFAULT = True


def analyze(ctx: ReviewContext) -> list[Finding]:
    out: list[Finding] = []
    for s in ctx.section("changed_symbols").get("symbols", []):
        if s.get("tests_before", 0) != 0:
            continue
        out.append(Finding(
            rule="CT002", severity=Severity.MEDIUM,
            title=f"`{s['name']}` changed but no test executed it",
            message=f"The {s.get('kind', 'symbol')} `{s['name']}` changed in this pull request, and none of the "
                    "recorded tests ran its lines on the base commit. A regression here would not be caught by any "
                    "test selection.",
            path=s.get("file"), start_line=s.get("start"), end_line=s.get("end"),
            evidence=[f"0 recorded tests executed `{s['name']}` at the base commit (or it is new in this change)"],
            suggestion=f"Add a test that calls `{s['name'].rsplit('.', 1)[-1]}`."))
    return out
