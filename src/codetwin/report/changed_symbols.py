"""Functions, methods and classes whose lines the change touches, with how many tests executed each before."""
from __future__ import annotations

from ..graph.symbols import changed_symbols

NAME = "changed_symbols"


def contribute(ctx) -> dict:
    facts = ctx.facts_now() if ctx.facts_now else {}
    syms = changed_symbols(facts, ctx.diff, ctx.prev, ctx.is_source, ctx.store.get_static(ctx.base))
    untested = [s for s in syms if s["tests_before"] == 0]
    return {"symbols": syms, "untested": [f"{s['file']}:{s['name']}" for s in untested],
            "summary": f"{len(syms)} changed symbols, {len(untested)} not executed by any test before the change"}
