"""Typed impact graph: which tests and modules a change reaches, and how each link is known."""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from ..evidence.model import EvidenceType, FileFacts, TestRun
from ..evidence.static import module_of


@dataclass
class Impact:
    tests: dict[str, set[str]] = field(default_factory=dict)       # test file -> evidence types linking it
    unknowns: list[str] = field(default_factory=list)              # what the analysis could not see


def build_graph(static: dict[str, FileFacts], run: TestRun | None, src_root: str) -> nx.MultiDiGraph:
    """Nodes are files; an edge u -> v means "u depends on v", labelled with its evidence type."""
    g = nx.MultiDiGraph()
    known = {module_of(f, src_root): f for f in static}
    for f, facts in static.items():
        g.add_node(f)
        for imp in facts.imports:
            parts = imp.split(".")
            for k in range(len(parts), 0, -1):
                tgt = known.get(".".join(parts[:k]))
                if tgt:
                    if tgt != f:
                        g.add_edge(f, tgt, type=EvidenceType.STATIC.value)
                    break
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
        for u, _, data in g.out_edges(f, data=True):
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
