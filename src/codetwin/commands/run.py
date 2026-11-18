"""`codetwin run`: run test files with the project's own test runner (any language)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ._util import engine

NAME, HELP, ORDER = "run", "run test files (default: the last selection) with the project's test runner", 37


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("tests", nargs="*", help="test files (default: the tests selected by the last `codetwin select`)")
    p.add_argument("--decision", help="run the tests selected in this `codetwin select --json` file; use this in CI: "
                                      "a decision that changed only tests is printed but not stored")
    p.add_argument("--timeout", type=int, default=3600, help="seconds per test file")


def _selected(path: str) -> list[str]:
    decision = json.loads(Path(path).read_text(encoding="utf-8"))
    selected = decision.get("selected") if isinstance(decision, dict) else None
    if not isinstance(selected, list) or not all(isinstance(t, str) for t in selected):
        raise RuntimeError(f"{path} is not `codetwin select --json` output (no list of selected tests)")
    return selected


def run(args: argparse.Namespace) -> int:
    with engine(args) as eng:
        if args.tests:
            tests = list(args.tests)
        elif args.decision:
            tests = _selected(args.decision)
        else:
            tests = list((eng.store.last_decision() or {}).get("selected", []))
        if not tests:
            print("no tests to run")
            return 0
        ok = eng.lang.run_all(eng.root, tests, args.timeout)
    print(f"{len(tests)} test file(s): {'passed' if ok else 'FAILED'}")
    return 0 if ok else 1
