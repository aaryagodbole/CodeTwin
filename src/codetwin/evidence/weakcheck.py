"""Weak-check evidence: changed functions that tests execute but do not check ("pseudo-tested").

For every function that encloses a changed line, the body is replaced by `return None` in a temporary
copy of the working tree (extreme mutation, Niedermayr et al.), and the test files that executed the
function in the recorded run are run against it. If they all still pass, the function is executed but
not checked: coverage-based evidence that "the tests cover this change" is weak there.

In the study (paper, Section 7), 122 of 216 history changes that line-coverage selection handled safely
had at least one changed line whose seeded fault no executing test detected.

This runs tests, so it is an explicit command (`codetwin weakcheck`), not part of every decision.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

IGNORE = shutil.ignore_patterns(".git", ".codetwin", "node_modules", "__pycache__", ".venv", "venv", ".tox", "*.pyc")


@dataclass
class FunctionCheck:
    file: str
    start: int                    # first line (decorators included) in the new version
    end: int
    tests: list[str] = field(default_factory=list)
    status: str = ""              # checked | unchecked | untested | error
    killers: list[str] = field(default_factory=list)


def _innermost(defs, line):
    best = None
    for d in defs:
        if d[0] <= line <= d[1] and (best is None or d[0] >= best[0]):
            best = d
    return best


def changed_functions(diff, prev_run, prev_static, now_static, is_source) -> list[FunctionCheck]:
    out: dict[tuple[str, int], FunctionCheck] = {}
    for f, d in diff.items():
        if not is_source(f) or d.status in ("A", "D"):
            continue
        now, old = now_static.get(f), prev_static.get(d.old_path or f)
        if now is None:
            continue
        old_fn_lines: set[int] = set()
        if old is not None:
            for line in d.old:
                fn = _innermost(old.defs, line)
                if fn:
                    old_fn_lines.update(range(fn[2], fn[1] + 1))
        tests = sorted(t for t, files in prev_run.covered.items() if set(files.get(d.old_path or f, [])) & old_fn_lines)
        for line in d.new:
            fn = _innermost(now.defs, line)
            if fn and (f, fn[0]) not in out:
                out[(f, fn[0])] = FunctionCheck(f, fn[0], fn[1], tests)
    return list(out.values())


def _mutate(src: str, body_first: int, end: int) -> str:
    lines = src.splitlines(keepends=True)
    body = lines[body_first - 1]
    indent = body[: len(body) - len(body.lstrip())]
    return "".join(lines[: body_first - 1] + [f"{indent}return None\n"] + lines[end:])


def run_checks(root: str | Path, src_root: str, checks: list[FunctionCheck], now_static, timeout: int = 300) -> list[FunctionCheck]:
    root = Path(root)
    with tempfile.TemporaryDirectory(prefix="codetwin-weak-") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(root, work, ignore=IGNORE)
        # no bytecode cache: two mutants of one file can have equal size and mtime, and a stale .pyc would be run
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join([str(work / src_root), os.environ.get("PYTHONPATH", "")]))
        for c in checks:
            if not c.tests:
                c.status = "untested"
                continue
            fn = _innermost(now_static[c.file].defs, c.start)
            target = work / c.file
            original = target.read_text(encoding="utf-8")
            try:
                target.write_text(_mutate(original, fn[2], fn[1]), encoding="utf-8")
                r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                                    *c.tests], cwd=work, env=env, capture_output=True, text=True, timeout=timeout)
                c.status = "unchecked" if r.returncode == 0 else ("checked" if r.returncode == 1 else "error")
                if c.status == "checked":
                    c.killers = sorted({ln.split("::")[0].split(" ")[-1] for ln in r.stdout.splitlines()
                                        if ln.startswith("FAILED ")})
            except subprocess.TimeoutExpired:
                c.status = "error"
            finally:
                target.write_text(original, encoding="utf-8")
    return checks
