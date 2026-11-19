"""`codetwin run`: run test files with the project's own test runner (any language)."""
from __future__ import annotations

import argparse

from ._util import engine
from .review import check_decision_files, load_decision

NAME, HELP, ORDER = "run", "run test files (default: the last selection) with the project's test runner", 37


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("tests", nargs="*", help="test files (default: the tests selected by the last `codetwin select`)")
    p.add_argument("--decision", help="run the tests selected in this `codetwin select --json` file (not together "
                                      "with test files); use it in CI, where the file travels between steps")
    p.add_argument("--timeout", type=int, default=3600, help="seconds per test file")


def run(args: argparse.Namespace) -> int:
    if args.tests and args.decision is not None:
        raise SystemExit("codetwin run: give test files or --decision, not both")
    with engine(args) as eng:
        if args.tests:
            tests = list(args.tests)
        elif args.decision is not None:
            decision = load_decision(args.decision)                  # same checks as `codetwin review --decision`
            # Check it against the change since its own base, so a decision made with `select --base` works too.
            saved = (decision.get("extras") or {}).get("changed_files")
            saved = saved if isinstance(saved, dict) else {}
            made_for = saved.get("base")
            if isinstance(made_for, str) and made_for:
                try:
                    check_decision_files(eng, saved, eng.changed(made_for))
                except RuntimeError:
                    raise SystemExit(f"--decision was computed against {made_for[:12]}, which is not in this "
                                     "repository; run `codetwin select --json` again") from None
            tests = list(decision["selected"])
        else:
            tests = list((eng.store.last_decision() or {}).get("selected", []))
        if not tests:
            print("no tests to run")
            return 0
        ok = eng.lang.run_all(eng.root, tests, args.timeout)
    print(f"{len(tests)} test file(s): {'passed' if ok else 'FAILED'}")
    return 0 if ok else 1
