"""Print the test-gap report without storing a decision."""
from __future__ import annotations

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


def add_arguments(p) -> None:
    p.add_argument("--base", help="recorded commit to compare with (default: latest recorded)")
    p.add_argument("--json", action="store_true", help="machine-readable output (same shape as extras.test_gaps)")


def run(args) -> int:
    with engine(args) as eng:
        try:
            base, prev, diff, rows = eng.analyse(args.base)
        except RuntimeError as exc:
            print(str(exc))
            return 1

        ctx = report.Context(
            cfg=eng.cfg, store=eng.store, base=base, prev=prev,
            diff=diff, rows=rows, scores={}, decision=None,
            is_source=eng.is_source, facts_now=eng.facts_now,
            lang=eng.lang,
        )
        gaps = test_gaps.contribute(ctx)

    if args.json:
        print_json(gaps)
        return 0

    files = gaps.get("files", {})
    if not files:
        print(gaps["summary"])
        return 0

    for path, info in sorted(files.items()):
        lines = info["lines"]
        changed = info["changed_lines"]
        syms = info.get("symbols", [])
        sym_text = f"  ({', '.join(syms)})" if syms else ""
        print(f"{path}  {len(lines)} of {changed} changed lines untested{sym_text}")
        print(f"  lines {_ranges(lines)}")

    print(gaps["summary"])
    return 0
