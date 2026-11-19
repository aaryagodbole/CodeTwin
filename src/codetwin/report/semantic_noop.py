"""Section: is the change a semantic no-op (docstring, comment or formatting only)?

For a no-op change only the added or changed tests need to run. The section is advisory: the
selection itself is unchanged (see evidence/noop.py for the definition and its limits). Docstrings
are stored in `__doc__`, so a docstring edit is a no-op only for code that does not read them at run
time; the summary says so.
"""
from __future__ import annotations

from ..evidence.noop import classify_change
from ..lang.base import Language

NAME = "semantic_noop"
PUBLISH = True    # paths, names and numbers only (docs/data-policy.md)


def contribute(ctx) -> dict:
    kind, files = classify_change(ctx.cfg.root, ctx.base, ctx.diff, ctx.is_source,
                                  ctx.lang.classify_source if ctx.lang is not None else None)
    forced = sorted(t for t, r in ctx.rows.items() if r.get("forced"))
    text = {"noop": getattr(ctx.lang, "noop_description", Language.noop_description),
            "annotation": "annotation-only change: low risk, but annotations can be read at run time, so tests still run",
            "semantic": "behaviour-changing edit",
            "no-source": "no source file changed"}[kind]
    return {"kind": kind, "files": files, "sufficient_tests": forced if kind == "noop" else None, "summary": text}
