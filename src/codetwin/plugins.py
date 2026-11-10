"""Auto-discovery of per-feature modules, so new features never edit a shared file.

Every module in a plugin package (``commands``, ``mcp_tools``, ``report``) is imported and used
automatically. Modules whose name starts with ``_`` are skipped (helpers).
"""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType


def discover(package: str) -> list[ModuleType]:
    pkg = importlib.import_module(package)
    mods = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if not info.name.startswith("_"):
            mods.append(importlib.import_module(f"{package}.{info.name}"))
    return mods
