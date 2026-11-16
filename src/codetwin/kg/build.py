"""Build the knowledge graph from recorded evidence: static facts, a test run and the commit history."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from itertools import combinations
from typing import Any

from ..evidence.model import FileFacts, TestRun
from ..graph.impact import file_deps
from .graph import KnowledgeGraph
from .schema import EdgeKind, NodeKind, node_id, symbol_key

MIN_CO_CHANGES = 2          # pairs committed together fewer times are noise
MAX_FILES_PER_COMMIT = 30   # bulk commits (renames, formatting) say nothing about coupling


def build(static: dict[str, FileFacts], run: TestRun | None = None, history: Iterable[list[str]] = (),
          is_test: Callable[[str], bool] = lambda p: False, src_root: str | None = None,
          repo: str = "self") -> KnowledgeGraph:
    """Pure function of its inputs, so it is easy to test and the result is reproducible."""
    kg = KnowledgeGraph(repo)
    rid = node_id(NodeKind.REPOSITORY, repo)
    tests = set(run.durations) | set(run.covered) if run else set()
    tests |= {f for f in static if is_test(f)}

    def file_node(path: str) -> str:
        kind = NodeKind.TEST if path in tests else NodeKind.FILE
        nid = kg.add_node(kind, path)
        kg.add_edge(rid, nid, EdgeKind.CONTAINS)
        return nid

    deps = file_deps(static, src_root)
    for path, facts in sorted(static.items()):
        fid = file_node(path)
        for name, kind, a, b in facts.symbols:
            sid = kg.add_node(NodeKind.SYMBOL, symbol_key(path, name), name=name, symbol_kind=kind, file=path,
                              start=int(a), end=int(b))
            kg.add_edge(fid, sid, EdgeKind.DEFINES)
        for dst in deps.get(path, []):
            if dst != path:
                kg.add_edge(fid, file_node(dst), EdgeKind.IMPORTS)
        if facts.dynamic:
            uid = kg.add_node(NodeKind.UNKNOWN, path, detail=f"dynamic calls ({', '.join(sorted(set(facts.dynamic)))})")
            kg.add_edge(fid, uid, EdgeKind.UNRESOLVED, lines=",".join(map(str, facts.dyn_lines[:50])))

    if run:
        for test in sorted(tests):
            file_node(test)
        for test, files in sorted(run.covered.items()):
            tid = node_id(NodeKind.TEST, test)
            for src, lines in sorted(files.items()):
                if not lines:
                    continue
                kg.add_edge(tid, file_node(src), EdgeKind.COVERS, lines=len(lines))
                hit = set(lines)
                for sid in kg.neighbours(node_id(NodeKind.FILE, src), EdgeKind.DEFINES):
                    n = kg.g.nodes[sid]
                    k = len(hit & set(range(n["start"], n["end"] + 1)))
                    if k:
                        kg.add_edge(tid, sid, EdgeKind.COVERS, lines=k)

    pairs: Counter[tuple[str, str]] = Counter()
    for commit in history:
        together = sorted({f for f in commit if f in static})
        if 1 < len(together) <= MAX_FILES_PER_COMMIT:
            pairs.update(combinations(together, 2))
    for (a, b), count in pairs.items():
        if count >= MIN_CO_CHANGES:
            kg.add_edge(file_node(a), file_node(b), EdgeKind.CO_CHANGES, commits=count)
            kg.add_edge(file_node(b), file_node(a), EdgeKind.CO_CHANGES, commits=count)
    return kg


def from_engine(eng: Any, sha: str | None = None) -> KnowledgeGraph:
    """The graph of a recorded commit (default: the latest recorded run) of an `Engine`'s project."""
    sha = sha or eng.store.latest_run_sha()
    if not sha:
        raise RuntimeError("no recorded run yet; run `codetwin record` first")
    static = eng.store.get_static(sha)
    run = eng.store.get_run(sha)
    return build(static, run, eng.history(), eng.lang.is_test, eng.cfg.src_root, repo=eng.root.name)
