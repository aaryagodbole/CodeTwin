"""CT003 and CT006: places where the evidence cannot see, taken from the decision's reasons.

The engine never drops an unresolved link (AGENTS.md: unknown is not "no dependency"); it states it in
`Decision.reasons`. This analyzer turns those statements into findings attached to their file.
"""
from __future__ import annotations

import re

from ..context import ReviewContext
from ..model import Finding, Severity

NAME = "blind_spots"
DEFAULT = True

# "<file>: dynamic calls (getattr) cannot be followed statically"  /  "<file>: new or unparsed file, no evidence yet"
_DYNAMIC = re.compile(r"^(?P<file>[^:\s]+): dynamic calls \((?P<kinds>[^)]*)\)")
_NO_EVIDENCE = re.compile(r"^(?P<file>[^:\s]+): new or unparsed file")


def analyze(ctx: ReviewContext) -> list[Finding]:
    out: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for reason in ctx.decision.get("reasons", []):
        reason = str(reason)
        if m := _DYNAMIC.match(reason):
            key = ("CT003", m["file"])
            if key not in seen:
                seen.add(key)
                out.append(Finding(
                    rule="CT003", severity=Severity.LOW,
                    title=f"Dynamic calls in `{m['file']}` hide part of the impact",
                    message="This file uses calls that cannot be resolved statically "
                            f"({m['kinds']}). Code reached through them is not in the impact graph, so the "
                            "selected tests may not cover everything this change affects.",
                    path=m["file"], evidence=[reason],
                    suggestion="Check callers reached through these dynamic calls, or record a run so runtime "
                               "coverage fills the gap."))
        elif m := _NO_EVIDENCE.match(reason):
            key = ("CT006", m["file"])
            if key not in seen:
                seen.add(key)
                out.append(Finding(
                    rule="CT006", severity=Severity.MEDIUM,
                    title=f"No recorded evidence for `{m['file']}`",
                    message="This file is new or could not be parsed at the base commit, so CodeTwin does not "
                            "know which tests depend on it.",
                    path=m["file"], evidence=[reason],
                    suggestion="Make sure a test exercises this file; after merging, run `codetwin record`."))
    return out
