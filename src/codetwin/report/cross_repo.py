"""Files and tests in connected repositories ([[repos]] in .codetwin.toml) that the change may affect."""
from __future__ import annotations

from ..crossrepo.analysis import for_change

NAME = "cross_repo"


def contribute(ctx) -> dict:
    return for_change(ctx.cfg, ctx.facts_now() if ctx.facts_now else {}, ctx.diff, ctx.is_source)
