"""`codetwin run`: run test files with the project's own test runner (any language)."""
from __future__ import annotations

from ._util import engine

NAME, HELP, ORDER = "run", "run test files (default: the last selection) with the project's test runner", 37


def add_arguments(p) -> None:
    p.add_argument("tests", nargs="*", help="test files (default: the tests selected by the last `codetwin select`)")
    p.add_argument("--timeout", type=int, default=3600, help="seconds per test file")


def run(args) -> int:
    with engine(args) as eng:
        tests = list(args.tests) or list((eng.store.get_state("last_decision") or {}).get("selected", []))
        if not tests:
            print("no tests to run")
            return 0
        ok = eng.lang.run_all(eng.root, tests, args.timeout)
    print(f"{len(tests)} test file(s): {'passed' if ok else 'FAILED'}")
    return 0 if ok else 1
