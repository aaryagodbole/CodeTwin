"""Typed impact graph: which tests and modules a change reaches, and how each link is known."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import networkx as nx

from ..evidence.model import EvidenceType, FileFacts, TestRun


@dataclass
class Impact:
    tests: dict[str, set[str]] = field(default_factory=dict)       # test file -> evidence types linking it
    unknowns: list[str] = field(default_factory=list)              # what the analysis could not see


def file_deps(static: dict[str, FileFacts], src_root: str | None = None) -> dict[str, list[str]]:
    """Dependencies of every file as file paths. Language adapters fill `FileFacts.deps`; facts without it
    (older stored snapshots, direct callers of `evidence.static`) are resolved as Python imports."""
    if src_root is not None and any(f.imports and not f.deps for f in static.values()):
        from ..lang.python import resolve_deps
        static = {f: replace(v, deps=list(v.deps)) for f, v in static.items()}
        resolve_deps(static, src_root)
    return {f: list(v.deps) for f, v in static.items()}


def build_graph(static: dict[str, FileFacts], run: TestRun | None, src_root: str | None = None) -> nx.MultiDiGraph:
    """Nodes are files; an edge u -> v means "u depends on v", labelled with its evidence type."""
    g: nx.MultiDiGraph = nx.MultiDiGraph()
    deps = file_deps(static, src_root)
    for f, facts in static.items():
        g.add_node(f)
        for tgt in deps[f]:
            if tgt != f:
                g.add_edge(f, tgt, type=EvidenceType.STATIC.value)
        if facts.dynamic:
            g.add_edge(f, "?", type=EvidenceType.UNRESOLVED.value, detail=",".join(facts.dynamic))
    if run:
        for test, files in run.covered.items():
            for src in files:
                g.add_edge(test, src, type=EvidenceType.RUNTIME.value)
    return g


def impact_of(g: nx.MultiDiGraph, changed: list[str], tests: list[str], max_depth: int = 6) -> Impact:
    """Tests that reach a changed file, with the evidence types on the way, plus unresolved links."""
    imp = Impact()
    rev = g.reverse(copy=False)
    for f in changed:
        if f not in g:
            imp.unknowns.append(f"{f}: new or unparsed file, no evidence yet")
            continue
        for _u, _, data in g.out_edges(f, data=True):
            if data["type"] == EvidenceType.UNRESOLVED.value:
                imp.unknowns.append(f"{f}: dynamic calls ({data.get('detail')}) cannot be followed statically")
        seen = {f: 0}
        frontier = [f]
        for depth in range(1, max_depth + 1):
            nxt = []
            for node in frontier:
                for _, src, data in rev.out_edges(node, data=True):
                    if src == "?":
                        continue
                    if src in tests:
                        imp.tests.setdefault(src, set()).add(data["type"])
                    if src not in seen and data["type"] == EvidenceType.STATIC.value:
                        seen[src] = depth
                        nxt.append(src)
            frontier = nxt
    return imp
