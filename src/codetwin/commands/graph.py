"""`codetwin graph FILE [--lines A-B]`: the impact graph around a file or selected lines (VS Code panel, dashboard)."""
from __future__ import annotations

from ..graph.view import impact_view
from ._util import engine, print_json

NAME, HELP, ORDER = "graph", "impact graph around a file or selected lines (nodes and typed edges)", 55


def add_arguments(p) -> None:
    p.add_argument("file", help="repository-relative path")
    p.add_argument("--lines", help="selected line range, e.g. 10-24")
    p.add_argument("--json", action="store_true")


def parse_lines(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    a, _, b = text.partition("-")
    lo, hi = int(a), int(b or a)
    return (min(lo, hi), max(lo, hi))


def build(eng, file: str, lines: tuple[int, int] | None) -> dict:
    ch = eng.change(require_run=False)
    run = ch.prev
    base = ch.base if run is not None else None
    view = impact_view(ch.facts_now, run, eng.cfg.src_root, ch.tests_now, file, lines)
    view["evidence"] = {"recorded_commit": base, "has_coverage": run is not None}
    if run is None:
        view["unknowns"].append("no recorded run: run `codetwin record` to add runtime evidence")
    return view


def run(args) -> int:
    with engine(args) as eng:
        view = build(eng, args.file, parse_lines(args.lines))
    if args.json:
        print_json(view)
        return 0
    print(f"{view['target']['id']}: {view['summary']}")
    for e in view["edges"]:
        print(f"  {e['source']} -> {e['target']}  [{e['type']}] {e.get('detail', '')}")
    for u in view["unknowns"]:
        print(f"UNKNOWN: {u}")
    return 0
