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

import ast
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
    baseline_failures: list[str] = field(default_factory=list)   # test files failing on the unmutated tree


def _innermost(defs, line):
    best = None
    for d in defs:
        if d[0] <= line <= d[1] and (best is None or d[0] >= best[0]):
            best = d
    return best


def changed_functions(diff, prev_run, prev_static, now_static, is_source) -> list[FunctionCheck]:
    out: dict[tuple[str, int], FunctionCheck] = {}
    for f, d in diff.items():
        if not is_source(f) or d.status == "D":
            continue
        now, old = now_static.get(f), prev_static.get(d.old_path or f)
        if now is None:
            continue
        old_fn_lines: set[int] = set()
        if old is not None and d.status != "A":   # an added file has no base facts and no executing tests
            for line in d.old:
                fn = _innermost(old.defs, line)
                if fn:
                    old_fn_lines.update(range(fn[2], fn[1] + 1))
        tests = sorted(t for t, files in prev_run.covered.items()
                       if set(files.get(d.old_path or f, [])) & old_fn_lines) if old_fn_lines else []
        for line in d.new:
            fn = _innermost(now.defs, line)
            if fn and (f, fn[0]) not in out:
                out[(f, fn[0])] = FunctionCheck(f, fn[0], fn[1], tests)
    return list(out.values())


def _mutate(src: str, def_start: int, body_first: int, end: int) -> str | None:
    """Replace the body of the function at lines def_start..end with `return None`.

    Uses the AST rather than line numbers alone: for a one-line function (`def f(): return x`) the body
    starts on the `def` line, so the header is kept and only the part after its colon is replaced.
    Returns None when the function cannot be located (the caller reports it as an error).
    """
    lines = src.splitlines(keepends=True)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    fn = next((n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.body and n.body[0].lineno == body_first and n.lineno >= def_start
               and (n.end_lineno or n.lineno) <= end), None)
    if fn is None:
        return None
    first, stop = fn.body[0], fn.end_lineno or end
    line = lines[first.lineno - 1]
    head = line[: _col_to_char(line, first.col_offset)]
    # `head` is the indentation, or for `def f(): return x` the whole header up to the body
    return "".join(lines[: first.lineno - 1] + [f"{head}return None\n"] + lines[stop:])


def _col_to_char(line: str, col: int) -> int:
    """AST column offsets count UTF-8 bytes; convert to a character index."""
    return len(line.encode("utf-8")[:col].decode("utf-8", errors="ignore"))


def _pytest(work: Path, env: dict, tests: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", *tests],
                          cwd=work, env=env, capture_output=True, text=True, timeout=timeout)


def _failed_files(stdout: str) -> set[str]:
    return {ln.split("::")[0].split(" ")[-1] for ln in stdout.splitlines() if ln.startswith(("FAILED ", "ERROR "))}


def run_checks(root: str | Path, src_root: str, checks: list[FunctionCheck], now_static, timeout: int = 300) -> list[FunctionCheck]:
    root = Path(root)
    with tempfile.TemporaryDirectory(prefix="codetwin-weak-") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(root, work, ignore=IGNORE)
        # no bytecode cache: two mutants of one file can have equal size and mtime, and a stale .pyc would be run
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join([str(work / src_root), os.environ.get("PYTHONPATH", "")]))
        # Baseline: test files that already fail on the unmutated tree cannot show that a mutant was caught.
        baseline: dict[str, bool] = {}
        for t in sorted({t for c in checks for t in c.tests}):
            try:
                baseline[t] = _pytest(work, env, [t], timeout).returncode == 0
            except subprocess.TimeoutExpired:
                baseline[t] = False
        for c in checks:
            c.baseline_failures = [t for t in c.tests if not baseline.get(t, False)]
            tests = [t for t in c.tests if baseline.get(t, False)]
            if not c.tests:
                c.status = "untested"
                continue
            if not tests:
                c.status = "error"     # every executing test file already fails: no evidence either way
                continue
            fn = _innermost(now_static[c.file].defs, c.start)
            target = work / c.file
            original = target.read_text(encoding="utf-8")
            mutant = _mutate(original, fn[0], fn[2], fn[1]) if fn else None
            if mutant is None:
                c.status = "error"
                continue
            try:
                target.write_text(mutant, encoding="utf-8")
                r = _pytest(work, env, tests, timeout)
                c.status = "unchecked" if r.returncode == 0 else ("checked" if r.returncode == 1 else "error")
                if c.status == "checked":
                    c.killers = sorted(_failed_files(r.stdout))
            except subprocess.TimeoutExpired:
                c.status = "error"
            finally:
                target.write_text(original, encoding="utf-8")
    return checks
