"""A small graph around one file or selected lines, for the editor panel and the dashboard.

Nodes: the target (file or line range), source files that import it, files it imports, tests and unknowns.
Each edge carries its evidence type, so the view can draw static, runtime and unresolved links differently.
"""
from __future__ import annotations

from ..evidence.model import EvidenceType, FileFacts, TestRun
from .impact import build_graph, impact_of


def label(path: str) -> str:
    """Short node label; package files keep their folder (`risk/__init__.py`)."""
    parts = path.split("/")
    return "/".join(parts[-2:]) if parts[-1] == "__init__.py" and len(parts) > 1 else parts[-1]


def impact_view(static: dict[str, FileFacts], run: TestRun | None, src_root: str, tests: list[str], file: str,
                lines: tuple[int, int] | None = None) -> dict:
    g = build_graph(static, run)
    target = f"{file}:{lines[0]}-{lines[1]}" if lines else file
    nodes: dict[str, dict] = {target: {"id": target, "label": label(target), "kind": "target", "path": file}}
    edges: list[dict] = []
    unknowns: list[str] = []

    def node(path: str, kind: str) -> None:
        nodes.setdefault(path, {"id": path, "label": label(path), "kind": kind, "path": path})

    def edge(src: str, dst: str, etype: str, detail: str = "") -> None:
        e = {"source": src, "target": dst, "type": etype}
        if detail:
            e["detail"] = detail
        if e not in edges:
            edges.append(e)

    if file not in g:
        unknowns.append(f"{file}: new or unparsed file, no evidence yet")
    facts = static.get(file)

    # tests that executed the selected lines (strongest evidence), else the file
    line_set = set(range(lines[0], lines[1] + 1)) if lines else None
    if run:
        for test, files in run.covered.items():
            hit = files.get(file)
            if hit is None:
                continue
            if line_set is None or line_set & set(hit):
                node(test, "test")
                edge(test, target, EvidenceType.RUNTIME.value,
                     "executes the selected lines" if line_set else "executes this file")

    # tests reached through imports (file level)
    imp = impact_of(g, [file], tests)
    for test, types in imp.tests.items():
        if test not in nodes:
            node(test, "test")
            for t in sorted(types):
                edge(test, target, t, "reaches this file")
    unknowns += [u for u in imp.unknowns if u not in unknowns]

    # direct importers (who depends on this file) and dependencies (what it imports)
    if file in g:
        for src, _, data in g.in_edges(file, data=True):
            if data["type"] == EvidenceType.STATIC.value and src not in tests and src != file:
                node(src, "source")
                edge(src, target, EvidenceType.STATIC.value, "imports this file")
        for _, dst, data in g.out_edges(file, data=True):
            if data["type"] == EvidenceType.STATIC.value and dst != file:
                node(dst, "source")
                edge(target, dst, EvidenceType.STATIC.value, "imported by this file")

    # dynamic calls inside the selection cannot be followed
    if facts and facts.dynamic:
        dyn = [ln for ln in facts.dyn_lines if line_set is None or ln in line_set]
        if dyn:
            uid = f"?{file}"
            nodes[uid] = {"id": uid, "label": "unresolved", "kind": "unknown", "path": file}
            edge(target, uid, EvidenceType.UNRESOLVED.value,
                 f"dynamic calls ({', '.join(facts.dynamic)}) on lines {', '.join(map(str, dyn))}")

    n_tests = sum(1 for n in nodes.values() if n["kind"] == "test")
    n_users = sum(1 for e in edges if e.get("detail") == "imports this file")
    n_unknown = len(unknowns)
    return {"target": nodes[target], "nodes": list(nodes.values()), "edges": edges, "unknowns": unknowns,
            "counts": {"tests": n_tests, "importers": n_users, "unknown": n_unknown},
            "summary": f"used by {n_users} · {n_tests} tests · {n_unknown} unknown"}
