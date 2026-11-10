"""Command-line interface: codetwin init | record | select | learn | impact | explain."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, config


def _print_decision(d, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"decision": d.decision, "residual_risk": round(d.residual_risk, 4), "threshold": d.threshold,
                          "mode": d.mode, "selected": sorted(d.selected), "reasons": d.reasons}, indent=1))
        return
    print(f"decision: {d.decision.upper()}   estimated residual risk: {d.residual_risk:.1%}   mode: {d.mode}")
    for r in d.reasons:
        print(f"  - {r}")
    print(f"selected {len(d.selected)} test files:")
    for t in sorted(d.selected):
        print(f"  {t}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="codetwin", description="Evidence-aware, risk-calibrated test selection.")
    ap.add_argument("--version", action="version", version=f"codetwin {__version__}")
    ap.add_argument("-C", "--root", default=".", help="repository root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="write .codetwin.toml with guessed settings")
    sub.add_parser("record", help="run the suite with per-test coverage on the current commit and store it")
    s = sub.add_parser("select", help="select tests for the changes since the recorded commit")
    s.add_argument("--base", help="recorded commit to compare with (default: latest recorded)")
    s.add_argument("--alpha", type=float, help="target miss rate (default from config)")
    s.add_argument("--budget", type=float, help="budget mode: share of full-suite time, e.g. 0.25")
    s.add_argument("--json", action="store_true")
    sub.add_parser("learn", help="run the full suite, record whether the last selection missed tests, update calibration")
    i = sub.add_parser("impact", help="tests and unknowns reached by changed files")
    i.add_argument("files", nargs="+")
    sub.add_parser("explain", help="evidence behind the last decision")
    a = ap.parse_args(argv)

    if a.cmd == "init":
        path = config.write_template(a.root)
        print(f"wrote {path}; review it, then run `codetwin record`")
        return 0
    from .engine import Engine
    eng = Engine(a.root)
    if a.cmd == "record":
        run = eng.record()
        print(f"recorded {run.sha[:10]}: {len(run.durations)} test files, {len(run.covered)} with coverage, "
              f"{len(run.failing)} failing test cases, {run.wall:.1f}s")
    elif a.cmd == "select":
        d = eng.select(a.base, a.alpha, a.budget)
        _print_decision(d, a.json)
    elif a.cmd == "learn":
        print(json.dumps(eng.learn(), indent=1))
    elif a.cmd == "impact":
        imp = eng.impact(a.files)
        for t, types in sorted(imp.tests.items()):
            print(f"{t}  [{', '.join(sorted(types))}]")
        for u in imp.unknowns:
            print(f"UNKNOWN: {u}")
    elif a.cmd == "explain":
        print(json.dumps(eng.explain(), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
