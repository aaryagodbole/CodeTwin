"""Run the analyzers and assemble one Review.

Order of a review: selection decision (engine) -> analyzers (evidence first, optional LLM last) ->
de-duplicate by fingerprint -> sort by severity -> per-file summary.
"""
from __future__ import annotations

from collections.abc import Iterable
from types import ModuleType

from ..plugins import discover
from .context import ReviewContext
from .model import FileSummary, Finding, Review

PACKAGE = "codetwin.review.analyzers"


def select_analyzers(enabled: Iterable[str] | None = None, disabled: Iterable[str] = ()) -> list[ModuleType]:
    """Analyzer modules to run: the defaults, or exactly `enabled` if given, minus `disabled`."""
    mods = discover(PACKAGE)
    names = set(enabled) if enabled is not None else {m.NAME for m in mods if getattr(m, "DEFAULT", True)}
    unknown = (names | set(disabled)) - {m.NAME for m in mods}
    if unknown:
        raise ValueError(f"unknown review analyzers: {', '.join(sorted(unknown))}")
    return [m for m in mods if m.NAME in names and m.NAME not in set(disabled)]


def run(ctx: ReviewContext, mods: list[ModuleType] | None = None) -> Review:
    mods = select_analyzers() if mods is None else mods
    findings: list[Finding] = []
    notes: list[str] = []
    for mod in mods:
        try:
            for f in mod.analyze(ctx):
                f.analyzer = mod.NAME
                findings.append(f)
        except Exception as e:  # noqa: BLE001 - one broken analyzer must not hide the others' findings
            notes.append(f"analyzer {mod.NAME} failed: {type(e).__name__}: {e}")
    seen: set[str] = set()
    unique = []
    for f in findings:
        if f.fingerprint not in seen:
            seen.add(f.fingerprint)
            unique.append(f)
    unique.sort(key=lambda f: (f.severity.rank, f.path or "", f.start_line or 0, f.rule))

    d = ctx.decision
    selected = sorted(d.get("selected", []))
    files = []
    covering = ctx.options.get("covering", {})        # file -> tests that covered it (optional, from the graph)
    for path, lines in sorted(ctx.changed.items()):
        files.append(FileSummary(path, len(lines), sorted(set(covering.get(path, [])) & set(selected)),
                                 sum(1 for f in unique if f.path == path)))
    alpha = getattr(ctx.cfg, "alpha", None)
    return Review(decision=str(d.get("decision", "proceed")), residual_risk=float(d.get("residual_risk", 0.0)),
                  alpha=alpha, selected=selected, findings=unique, files=files, notes=notes)
