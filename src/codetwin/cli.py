"""Command-line interface. Commands live in ``codetwin/commands/`` (one file each, auto-discovered)."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .plugins import discover


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="codetwin", description="Evidence-aware, risk-calibrated test selection.")
    ap.add_argument("--version", action="version", version=f"codetwin {__version__}")
    ap.add_argument("-C", "--root", default=".", help="repository root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for mod in sorted(discover("codetwin.commands"), key=lambda m: (getattr(m, "ORDER", 100), m.NAME)):
        p = sub.add_parser(mod.NAME, help=mod.HELP)
        mod.add_arguments(p)
        p.set_defaults(_run=mod.run)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args._run(args) or 0)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"codetwin: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
