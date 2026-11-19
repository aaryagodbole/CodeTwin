"""Weak-check evidence: changed functions that tests execute but do not check ("pseudo-tested").

For every function that encloses a changed line, the body is replaced by `return None` (in other languages:
an early return of a default value, see the language spec) in a temporary copy of the working tree (extreme mutation, Niedermayr et al.), and the test files that executed the
function in the recorded run are run against it. If they all still pass, the function is executed but
not checked: coverage-based evidence that "the tests cover this change" is weak there.

In the study (paper, Section 7), 105 of 209 history changes that line-coverage selection handled safely
had at least one covered changed line whose seeded fault no executing test detected.

This runs tests, so it is an explicit command (`codetwin weakcheck`), not part of every decision.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FunctionCheck:
    file: str
    start: int                    # first line (decorators included) in the new version
    end: int
    tests: list[str] = field(default_factory=list)
    status: str = ""              # checked | unchecked | untested | unsupported | error
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


def run_checks(root: str | Path, src_root: str, checks: list[FunctionCheck], now_static, timeout: int = 300,
               lang=None) -> list[FunctionCheck]:
    """Mutate each changed function in a scratch copy and run the test files that executed it.
    `lang` is the project's language adapter (it builds the mutants and runs the tests)."""
    if lang is None:
        raise ValueError("run_checks needs the project's language adapter (Engine.lang)")
    root = Path(root)
    with tempfile.TemporaryDirectory(prefix="codetwin-weak-") as tmp:
        work = Path(tmp) / "repo"
        lang.make_copy(work)
        # Baseline: test files that already fail on the unmutated tree cannot show that a mutant was caught.
        wanted = sorted({t for c in checks for t in c.tests})
        baseline = lang.run_tests(work, wanted, timeout) if wanted else {}
        for c in checks:
            c.baseline_failures = [t for t in c.tests if baseline.get(t) is not True]
            tests = [t for t in c.tests if baseline.get(t) is True]
            if not c.tests:
                c.status = "untested"
                continue
            if not tests:
                c.status = "error"     # every executing test file already fails: no evidence either way
                continue
            fn = _innermost(now_static[c.file].defs, c.start)
            target = work / c.file
            original = target.read_text(encoding="utf-8")
            mutant = lang.extreme_mutant(original, fn, c.file) if fn else None
            if mutant is None:
                # an adapter that can mutate every function failed on this one: an error, not a gap in support
                c.status = "error" if not fn or lang.mutates_every_function else "unsupported"
                continue
            try:
                target.write_text(mutant, encoding="utf-8")
                if not lang.build_ok(work, timeout):
                    c.status = "error"     # the mutant does not compile: says nothing about the tests
                    continue
                res = lang.run_tests(work, tests, timeout)
                if any(v is False for v in res.values()):
                    c.status = "checked"
                    c.killers = sorted(t for t, v in res.items() if v is False)
                elif all(v is True for v in res.values()):
                    c.status = "unchecked"
                else:
                    c.status = "error"
            finally:
                target.write_text(original, encoding="utf-8")
    return checks
