"""Report sections added to every decision (auto-discovered).

A section module defines::

    NAME = "test_gaps"                          # key in Decision.extras and under "extras" in select --json
    def contribute(ctx: Context) -> dict: ...   # JSON-serialisable; put a one-line text in "summary"
    PUBLISH = True                              # optional: upload this section with `codetwin push`

``PUBLISH = True`` opts a section into reports sent to CodeTwin Cloud (docs/cloud.md). Only sections that hold
file paths, symbol names, line numbers, counts and their summary may opt in; never source text. The default is
not to upload (docs/data-policy.md).

Sections only read the context; they must not change the selection or the decision (that is
``selection.py``). Add a new file here for a new section; do not edit ``engine.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..plugins import discover


@dataclass
class Context:
    """Everything known when a decision is made. Only pre-change evidence (no look-ahead)."""
    cfg: Any                      # codetwin.config.Config
    store: Any                    # codetwin.store.db.Store
    base: str                     # recorded commit the change is compared with
    prev: Any                     # TestRun recorded at base
    diff: dict                    # file -> FileDiff (changed lines)
    rows: dict                    # test -> feature row
    scores: dict                  # test -> risk score
    decision: Any                 # codetwin.selection.Decision
    is_source: Any                # callable(path) -> bool
    facts_now: Any = None         # callable() -> static facts of the working tree
    impact: Any = None            # callable(files) -> Impact
    lang: Any = None              # codetwin.lang.base.Language of the project
    extra: dict = field(default_factory=dict)


def publishable() -> set[str]:
    """Names of sections that opted in to `codetwin push` with ``PUBLISH = True``."""
    return {mod.NAME for mod in discover("codetwin.report") if getattr(mod, "PUBLISH", False) is True}


def build(ctx: Context) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for mod in discover("codetwin.report"):
        try:
            out[mod.NAME] = mod.contribute(ctx)
        except Exception as e:  # noqa: BLE001 - a broken section must be visible, not silently missing
            out[mod.NAME] = {"error": f"{type(e).__name__}: {e}", "summary": f"section failed: {e}"}
    return out
