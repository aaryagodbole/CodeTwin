"""The seven per-test features of a change (Section IV-C of the paper).

All of them use only evidence available before the change's tests run: the previous run's coverage
and times, the new version's static facts and the diff.
"""
from __future__ import annotations

from collections import Counter

from ..evidence.model import FileDiff, FileFacts, TestRun
from ..graph.impact import file_deps

FEATURES = ["cov_line", "cov_func", "cov_file", "static_inv_dist", "name_match", "cochange", "test_changed"]


def _innermost(defs, line):
    best = None
    for d in defs:
        if d[0] <= line <= d[1] and (best is None or d[0] >= best[0]):
            best = d
    return best


def _distance(test: str, changed: set[str], deps: dict[str, list[str]], max_depth: int = 6) -> int | None:
    """Length of the shortest import path from `test` to a changed file (None beyond `max_depth`)."""
    frontier, seen = set(deps.get(test, ())), set()
    for d in range(1, max_depth + 1):
        if frontier & changed:
            return d
        seen |= frontier
        nxt: set[str] = set()
        for f in frontier:
            nxt |= set(deps.get(f, ()))
        frontier = nxt - seen
        if not frontier:
            return None
    return None


def _py_stem(path: str) -> str:
    return path.rsplit("/", 1)[-1][:-3]


def compute(diff: dict[str, FileDiff], prev_run: TestRun, prev_static: dict[str, FileFacts],
            new_static: dict[str, FileFacts], tests: list[str], src_root: str, is_source,
            history: list[list[str]] | None = None, stem=_py_stem) -> dict[str, dict]:
    """Feature rows for every test file. `is_source(path)` tells source files from tests;
    `history` is a list of file lists of earlier commits (for co-change); `stem(path)` gives the module name
    used by the name-match feature."""
    changed = [(f, d) for f, d in diff.items() if is_source(f)]
    changed_tests = {f for f, d in diff.items() if not is_source(f) and d.status != "D"}
    deps = file_deps(new_static, src_root)
    changed_files = {f for f, _ in changed}
    stems = {stem(f) for f, _ in changed} - {"__init__"}
    co: Counter[str] = Counter()
    base = 0
    for files in (history or [])[-300:]:
        if set(files) & {f for f, _ in changed}:
            base += 1
            co.update(files)
    func_lines, outside = {}, {}
    for _f, d in changed:
        defs = prev_static.get(d.old_path, FileFacts()).defs
        fl: set[int] = set()
        out: set[int] = set()
        for line in d.old:
            D = _innermost(defs, line)
            fl.update(range(D[2], D[1] + 1)) if D else out.add(line)
        func_lines[d.old_path], outside[d.old_path] = fl, out
    rows = {}
    for t in tests:
        cl = cfn = cf = 0
        for _f, d in changed:
            lines = set(prev_run.covered.get(t, {}).get(d.old_path, []))
            if not lines:
                continue
            cf = 1
            imp = set(prev_run.import_lines.get(d.old_path, []))
            if set(d.old) & lines or set(d.old) & imp:
                cl = 1
            if func_lines[d.old_path] & lines or outside[d.old_path] & (lines | imp):
                cfn = 1
        dist = _distance(t, changed_files, deps)
        rows[t] = {"cov_line": cl, "cov_func": cfn, "cov_file": cf,
                   "static_inv_dist": 0.0 if dist is None else 1.0 / dist,
                   "name_match": int(any(s and s in t.rsplit("/", 1)[-1] for s in stems)),
                   "cochange": co.get(t, 0) / base if base else 0.0,
                   "test_changed": int(t in changed_tests),
                   # forced: changed in this commit, or new (unknown to the previous run's timing AND coverage)
                   "forced": t in changed_tests or (t not in prev_run.durations and t not in prev_run.covered),
                   "static_reach": dist is not None}
    return rows
