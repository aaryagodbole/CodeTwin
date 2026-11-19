"""Print the test-gap report without storing a decision."""
from __future__ import annotations

import argparse
import sys

from .. import report
from ..report import test_gaps
from ._util import engine, print_json

NAME, HELP, ORDER = "gaps", "changed lines no recorded test ran (no decision is stored)", 41


def _ranges(lines: list[int]) -> str:
    """Merge consecutive line numbers into compact ranges.

    >>> _ranges([1, 2, 3, 7])
    '1-3, 7'
    >>> _ranges([5])
    '5'
    """
    if not lines:
        return ""
    parts: list[str] = []
    start = prev = lines[0]
    for ln in lines[1:]:
        if ln == prev + 1:
            prev = ln
        else:
            parts.append(f"{start}-{prev}" if prev > start else str(start))
            start = prev = ln
    parts.append(f"{start}-{prev}" if prev > start else str(start))
    return ", ".join(parts)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--base", help="recorded commit to compare with (default: latest recorded)")
    p.add_argument("--json", action="store_true", help="machine-readable output (same shape as extras.test_gaps)")


def run(args: argparse.Namespace) -> int:
    with engine(args) as eng:
        # Only what the section needs: no test listing, history or feature rows, and nothing is stored.
        # Nothing recorded raises RuntimeError; the CLI prints it on stderr and exits with 2, like every command.
        ctx = eng.report_context(eng.change(args.base), None, rows={}, scores={})
        # Through report.build, so a failing section gives the same {"error", "summary"} as in `select`.
        gaps = report.build(ctx, only={test_gaps.NAME})[test_gaps.NAME]

    failed = "error" in gaps
    if args.json:
        print_json(gaps)
        return 1 if failed else 0
    if failed:
        print(f"codetwin gaps: {gaps['summary']}", file=sys.stderr)
        return 1

    for path, info in sorted(gaps.get("files", {}).items()):
        lines = info["lines"]
        syms = info.get("symbols", [])
        sym_text = f"  ({', '.join(syms)})" if syms else ""
        # changed_lines counts every added line (blank lines and comments too), lines only code lines.
        print(f"{path}  {len(lines)} untested code lines ({info['changed_lines']} lines changed){sym_text}")
        print(f"  lines {_ranges(lines)}")
    print(gaps["summary"])
    return 0
