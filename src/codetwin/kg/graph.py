"""The knowledge graph and its queries."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from .schema import EVIDENCE, EdgeKind, NodeKind, node_id, symbol_key


@dataclass
class BlastRadius:
    """What a change can affect, each item with the chain of evidence that links it to the change."""
    symbols: list[str] = field(default_factory=list)            # changed symbols (node ids)
    files: dict[str, list[str]] = field(default_factory=dict)   # dependent source file -> import chain to a change
    tests: dict[str, list[str]] = field(default_factory=dict)   # test -> evidence kinds linking it
    unknowns: list[str] = field(default_factory=list)           # unresolved dependencies on the way

    def to_dict(self) -> dict[str, Any]:
        return {"symbols": self.symbols, "files": self.files, "tests": {t: sorted(v) for t, v in self.tests.items()},
                "unknowns": self.unknowns}


class KnowledgeGraph:
    """A typed MultiDiGraph. Node attribute `kind` is a NodeKind value; edge attribute `kind` an EdgeKind value
    and `evidence` the evidence type it came from."""

    def __init__(self, repo: str = "self") -> None:
        self.g: nx.MultiDiGraph = nx.MultiDiGraph()
        self.repo = repo
        self.add_node(NodeKind.REPOSITORY, repo)

    # ------------------------------------------------------------- construction
    def add_node(self, kind: NodeKind, key: str, **attrs: Any) -> str:
        nid = node_id(kind, key)
        if nid in self.g:
            self.g.nodes[nid].update(attrs)
        else:
            self.g.add_node(nid, kind=kind.value, key=key, **attrs)
        return nid

    def add_edge(self, src: str, dst: str, kind: EdgeKind, **attrs: Any) -> None:
        existing: dict[Any, dict] = self.g.get_edge_data(src, dst, default={}) or {}
        if not any(d.get("kind") == kind.value for d in existing.values()):
            self.g.add_edge(src, dst, kind=kind.value, evidence=EVIDENCE[kind], **attrs)

    # ------------------------------------------------------------- inspection
    def nodes(self, kind: NodeKind | None = None) -> list[str]:
        return sorted(n for n, d in self.g.nodes(data=True) if kind is None or d.get("kind") == kind.value)

    def edges(self, kind: EdgeKind | None = None) -> list[tuple[str, str, dict]]:
        return sorted(((u, v, d) for u, v, d in self.g.edges(data=True) if kind is None or d.get("kind") == kind.value),
                      key=lambda e: (e[0], e[1], e[2].get("kind", "")))

    def stats(self) -> dict[str, Any]:
        nk: dict[str, int] = {}
        ek: dict[str, int] = {}
        for _, d in self.g.nodes(data=True):
            nk[d["kind"]] = nk.get(d["kind"], 0) + 1
        for _, _, d in self.g.edges(data=True):
            ek[d["kind"]] = ek.get(d["kind"], 0) + 1
        return {"nodes": self.g.number_of_nodes(), "edges": self.g.number_of_edges(),
                "node_kinds": dict(sorted(nk.items())), "edge_kinds": dict(sorted(ek.items()))}

    def neighbours(self, nid: str, kind: EdgeKind | None = None, incoming: bool = False) -> list[str]:
        if nid not in self.g:
            return []
        it = self.g.in_edges(nid, data=True) if incoming else self.g.out_edges(nid, data=True)
        return sorted({(u if incoming else v) for u, v, d in it if kind is None or d.get("kind") == kind.value})

    # ------------------------------------------------------------- queries
    def symbols_at(self, path: str, lines: list[int] | set[int]) -> list[str]:
        """Innermost symbols of `path` whose span contains one of `lines`; no lines = the file's top-level symbols."""
        defined = self.neighbours(node_id(NodeKind.FILE, path), EdgeKind.DEFINES)
        if not lines:
            return [s for s in defined if not any(o != s and self._inside(s, o) for o in defined)]
        ls = set(lines)
        hit = [s for s in defined
               if ls & set(range(self.g.nodes[s].get("start", 0), self.g.nodes[s].get("end", -1) + 1))]
        return [s for s in hit if not any(o != s and self._inside(o, s) for o in hit)]

    def _inside(self, inner: str, outer: str) -> bool:
        i, o = self.g.nodes[inner], self.g.nodes[outer]
        return o["start"] <= i["start"] and i["end"] <= o["end"] and (i["start"], i["end"]) != (o["start"], o["end"])

    def blast_radius(self, changed: dict[str, list[int]], max_depth: int = 4) -> BlastRadius:
        """Symbols the change touches, files that import a changed file (transitively, up to `max_depth`), the
        tests that covered any of them on the recorded commit, and unresolved links on the way.

        `changed` maps a path to line numbers **of the recorded commit** (FileDiff.old), because the graph
        describes that commit: its symbol spans and coverage are the evidence a selection may use."""
        br = BlastRadius()
        start = []
        for path, lines in sorted(changed.items()):
            fid = node_id(NodeKind.FILE, path)
            if fid not in self.g:
                if node_id(NodeKind.TEST, path) not in self.g:
                    br.unknowns.append(f"{path}: not in the graph (new or unparsed file)")
                continue
            start.append(fid)
            br.symbols += self.symbols_at(path, lines)
        prev: dict[str, str | None] = {s: None for s in start}
        q = deque((s, 0) for s in start)
        while q:
            n, depth = q.popleft()
            for u in self.neighbours(n, EdgeKind.UNRESOLVED):
                msg = f"{self.g.nodes[n]['key']}: {self.g.nodes[u].get('detail', 'dynamic calls')} cannot be followed"
                if msg not in br.unknowns:
                    br.unknowns.append(msg)
            if depth >= max_depth:
                continue
            for imp in self.neighbours(n, EdgeKind.IMPORTS, incoming=True):
                if imp not in prev:
                    prev[imp] = n
                    q.append((imp, depth + 1))
        for f in prev:
            if prev[f] is not None and self.g.nodes[f]["kind"] == NodeKind.FILE.value:
                chain: list[str] = []
                cur: str | None = f
                while cur is not None:
                    chain.append(self.g.nodes[cur]["key"])
                    cur = prev[cur]
                br.files[self.g.nodes[f]["key"]] = chain
        targets = set(prev) | set(br.symbols)
        for t in self.nodes(NodeKind.TEST):
            ev = {d["evidence"] for _, v, d in self.g.out_edges(t, data=True)
                  if d.get("kind") == EdgeKind.COVERS.value and v in targets}
            if ev:
                br.tests[self.g.nodes[t]["key"]] = sorted(ev)
        return br

    def context(self, changed: dict[str, list[int]], limit: int = 40) -> str:
        """A short, factual description of the change's neighbourhood, for a language model's prompt
        (graph-based retrieval: follow typed edges instead of guessing by text similarity)."""
        br = self.blast_radius(changed)
        lines = ["Changed symbols:"] + [f"- {self.g.nodes[s]['key']} ({self.g.nodes[s].get('symbol_kind')}, "
                                         f"covered by {len(self.neighbours(s, EdgeKind.COVERS, incoming=True))} tests)"
                                         for s in br.symbols[:limit]]
        lines += ["Files that depend on the changed files:"] + [f"- {f} (via {' <- '.join(reversed(c))})"
                                                               for f, c in list(br.files.items())[:limit]]
        lines += ["Tests that executed the changed code:"] + [f"- {t}" for t in list(br.tests)[:limit]]
        if br.unknowns:
            lines += ["Unresolved (impact may be larger):"] + [f"- {u}" for u in br.unknowns[:limit]]
        return "\n".join(lines)


__all__ = ["BlastRadius", "KnowledgeGraph", "symbol_key"]
