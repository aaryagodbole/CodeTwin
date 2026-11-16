"""Node and edge types of the knowledge graph, and how node ids are formed.

Every kind listed here is populated by `kg/build.py`. Add a kind only together with the code that fills it.
"""
from __future__ import annotations

from enum import StrEnum


class NodeKind(StrEnum):
    REPOSITORY = "repository"
    FILE = "file"            # a source file
    TEST = "test"            # a test file
    SYMBOL = "symbol"        # function, method or class (attribute `symbol_kind`)
    UNKNOWN = "unknown"      # a dependency that cannot be resolved (dynamic call); kept, never dropped


class EdgeKind(StrEnum):
    CONTAINS = "contains"        # repository -> file/test
    DEFINES = "defines"          # file -> symbol
    IMPORTS = "imports"          # file -> file          evidence: static
    COVERS = "covers"            # test -> file/symbol   evidence: runtime (lines executed on the recorded commit)
    CO_CHANGES = "co_changes"    # file -> file          evidence: co-change (committed together, both directions)
    UNRESOLVED = "unresolved"    # file -> unknown       evidence: unresolved


EVIDENCE = {EdgeKind.IMPORTS: "static", EdgeKind.COVERS: "runtime", EdgeKind.CO_CHANGES: "co-change",
            EdgeKind.UNRESOLVED: "unresolved", EdgeKind.DEFINES: "static", EdgeKind.CONTAINS: "structure"}


def node_id(kind: NodeKind, key: str) -> str:
    """`file:src/shop/price.py`, `symbol:src/shop/price.py::Cart.total`, `test:tests/test_price.py`."""
    return f"{kind.value}:{key}"


def symbol_key(path: str, qualname: str) -> str:
    return f"{path}::{qualname}"
