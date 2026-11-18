"""Example section: changed source files and how many lines changed in each."""
from __future__ import annotations

NAME = "changed_files"
PUBLISH = True    # paths, names and numbers only (docs/data-policy.md)


def contribute(ctx) -> dict:
    files = {f: len(d.new) for f, d in ctx.diff.items() if ctx.is_source(f)}
    return {"files": files, "base": ctx.base, "summary": f"{len(files)} source files, {sum(files.values())} changed lines"}
