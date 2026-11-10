"""Helpers shared by command modules."""
from __future__ import annotations

import json


def engine(args):
    from ..engine import Engine
    return Engine(args.root)


def print_json(obj) -> None:
    print(json.dumps(obj, indent=1, default=sorted))
