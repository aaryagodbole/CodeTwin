"""Breaking OpenAPI / JSON-schema changes in the change, with the code and tests that may rely on them."""
from __future__ import annotations

from ..contracts import for_change

NAME = "contracts"


def contribute(ctx) -> dict:
    return for_change(ctx.cfg, ctx.lang, ctx.base)
