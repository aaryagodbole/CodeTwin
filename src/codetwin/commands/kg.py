"""`codetwin kg`: the code knowledge graph of the recorded commit (stats, export, blast radius)."""
from __future__ import annotations

import argparse

from ._util import engine, print_json

NAME, HELP, ORDER = "kg", "knowledge graph of files, symbols and tests: stats, export (json/graphml), blast radius", 54


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", choices=["stats", "export", "blast"], help="what to do")
    p.add_argument("targets", nargs="*", help="blast: files or file:line (line numbers of the recorded commit)")
    p.add_argument("--sha", help="recorded commit (default: latest recorded run)")
    p.add_argument("--format", choices=["json", "graphml"], default="json", help="export format")
    p.add_argument("-o", "--output", help="export: output file (default: codetwin-graph.<format>)")
    p.add_argument("--depth", type=int, default=4, help="blast: how many import hops to follow")


def _targets(items: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for t in items:
        path, _, line = t.rpartition(":") if t.rpartition(":")[2].isdigit() else (t, "", "")
        out.setdefault(path, [])
        if line:
            out[path].append(int(line))
    return out


def run(args: argparse.Namespace) -> int:
    from ..kg import from_engine
    from ..kg.export import write

    with engine(args) as eng:
        kg = from_engine(eng, args.sha)
        if args.action == "stats":
            print_json(kg.stats())
        elif args.action == "export":
            path = write(kg, args.output or f"codetwin-graph.{args.format}", args.format)
            print(f"wrote {path} ({kg.stats()['nodes']} nodes, {kg.stats()['edges']} edges)")
        else:
            # a bare file (no line) means the whole file
            print_json(kg.blast_radius(_targets(args.targets), args.depth).to_dict())
    return 0
