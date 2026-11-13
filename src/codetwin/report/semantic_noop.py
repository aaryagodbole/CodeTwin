"""Section: is the change a semantic no-op (docstring, comment or formatting only)?

For a no-op change only the added or changed tests need to run. The section is advisory: the
selection itself is unchanged (see evidence/noop.py for the definition and its limits).
"""
from __future__ import annotations

from ..evidence.noop import classify_change

NAME = "semantic_noop"


def contribute(ctx) -> dict:
    kind, files = classify_change(ctx.cfg.root, ctx.base, ctx.diff, ctx.is_source)
    forced = sorted(t for t, r in ctx.rows.items() if r.get("forced"))
    text = {"noop": "semantic no-op (AST unchanged apart from docstrings/comments/formatting): only added or changed tests are needed",
            "annotation": "annotation-only change: low risk, but annotations can be read at run time, so tests still run",
            "semantic": "behaviour-changing edit",
            "no-source": "no source file changed"}[kind]
    return {"kind": kind, "files": files, "sufficient_tests": forced if kind == "noop" else None, "summary": text}
