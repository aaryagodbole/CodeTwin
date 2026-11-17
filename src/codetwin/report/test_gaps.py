"""Section: changed lines that ran under no test before the change (test gaps).

Two rules identify test gaps (reported as 1-based line numbers in the working tree):
1. New or untested functions: changed lines inside functions, methods or classes
   with `tests_before == 0` (via `codetwin.graph.symbols.changed_symbols`).
2. Edited lines inside tested functions: lines from diff hunks where the
   corresponding old line was neither covered by any test (`ctx.prev.covered`)
   nor executed at import time (`ctx.prev.import_lines`). For unequal-length
   additions (`nc > oc`), added lines are gaps if none of the hunk's old lines
   (or neighboring line for pure insertions) were covered or imported.

Skipped lines (never reported as gaps):
- Import-time lines: `def` headers and module-level constants executed at import.
- Comments and blank lines: lines that are empty or start with `#`.
- Docstrings: docstring line spans (parsed via `ast`).

Output shape:
    "test_gaps": {
      "files": {
        "src/shop/calc.py": {
          "lines": [9, 10, 11],
          "changed_lines": 6,
          "symbols": ["discount"]
        }
      },
      "summary": "3 of 6 changed lines in 1 file ran under no test"
    }

Only files that have gaps are included in `files`.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Any

from ..evidence.diff import git
from ..graph.symbols import changed_symbols, symbols_of

NAME = "test_gaps"


def _docstring_lines(text: str) -> set[int]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    out: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            out.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return out


def _read_old_lines(repo: Path, base: str, old_path: str) -> list[str]:
    try:
        return git(repo, "show", f"{base}:{old_path}").splitlines()
    except (RuntimeError, subprocess.SubprocessError, OSError):
        return []


def _read_working_lines(repo: Path, path: str) -> list[str]:
    try:
        return (repo / path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _is_code(lines: list[str], ln: int) -> bool:
    if not lines or ln < 1 or ln > len(lines):
        return True
    s = lines[ln - 1].strip()
    return bool(s and not s.startswith("#"))


def _enclosing_sym(facts: dict, path: str, ln: int) -> str | None:
    syms = [s for s in symbols_of(facts, path) if s.start <= ln <= s.end]
    if not syms:
        return None
    return min(syms, key=lambda s: s.end - s.start).name


def contribute(ctx: Any) -> dict:
    if ctx.prev is None:
        return {"files": {}, "summary": "no recorded test run"}

    repo = Path(ctx.cfg.root) if ctx.cfg and ctx.cfg.root else Path(".")
    facts = ctx.facts_now() if ctx.facts_now else {}
    base_facts = ctx.store.get_static(ctx.base) if (ctx.store and ctx.base) else None

    # Rule 1: find changed symbols with tests_before == 0
    syms = changed_symbols(facts, ctx.diff, ctx.prev, ctx.is_source, base_facts)
    untested_syms = [s for s in syms if s.get("tests_before", 0) == 0]

    # Pre-index covered lines and import-time lines at base
    covered_lines: dict[str, set[int]] = {}
    if ctx.prev.covered:
        for test_cov in ctx.prev.covered.values():
            for f, lns in test_cov.items():
                covered_lines.setdefault(f, set()).update(lns)

    import_lines: dict[str, set[int]] = {}
    if ctx.prev.import_lines:
        for f, lns in ctx.prev.import_lines.items():
            import_lines.setdefault(f, set()).update(lns)

    files_out: dict[str, dict] = {}
    total_changed = 0

    for path, d in sorted(ctx.diff.items()):
        if not ctx.is_source(path) or d.status == "D":
            continue

        old_path = d.old_path or path
        new_text_lines = _read_working_lines(repo, path)
        new_text = "\n".join(new_text_lines)
        old_text_lines = _read_old_lines(repo, ctx.base, old_path) if ctx.base else []
        old_text = "\n".join(old_text_lines)

        new_docstrings = _docstring_lines(new_text) if path.endswith(".py") else set()
        old_docstrings = _docstring_lines(old_text) if old_path.endswith(".py") else set()

        file_covered = covered_lines.get(old_path, set())
        file_imports = import_lines.get(old_path, set())

        # Build actual changed lines excluding deletion anchors (range(ns, ns + nc))
        actual_new_lines: set[int] = set()
        file_changed_count = 0
        if d.hunks:
            for _, _, ns, nc in d.hunks:
                if nc > 0:
                    actual_new_lines.update(range(ns, ns + nc))
                    file_changed_count += nc
        else:
            actual_new_lines = set(d.new)
            file_changed_count = len(d.new)

        total_changed += file_changed_count

        gap_lines: set[int] = set()
        gap_symbols: set[str] = set()

        if d.status == "A":
            # New file: all non-empty, non-comment, non-docstring lines are gaps
            for ln in sorted(actual_new_lines):
                if ln not in new_docstrings and _is_code(new_text_lines, ln):
                    gap_lines.add(ln)
            for s in syms:
                if s.get("file") == path:
                    gap_symbols.add(s["name"])
        else:
            # Rule 1: changed lines inside untested symbols (excluding import-time lines)
            file_untested = [s for s in untested_syms if s.get("file") == path]
            for s in file_untested:
                s_start, s_end = s["start"], s["end"]
                for ln in sorted(actual_new_lines):
                    if (
                        s_start <= ln <= s_end
                        and ln not in new_docstrings
                        and _is_code(new_text_lines, ln)
                        and ln not in file_imports
                    ):
                        gap_lines.add(ln)
                        gap_symbols.add(s["name"])

            # Rule 2: Edited and added lines inside tested functions / hunks
            for (os_, oc, ns, nc) in d.hunks:
                if nc == 0:
                    continue

                # 1) Pair the first min(oc, nc) lines
                paired_count = min(oc, nc)
                for i in range(paired_count):
                    old_ln = os_ + i
                    new_ln = ns + i

                    if new_ln in new_docstrings or not _is_code(new_text_lines, new_ln):
                        continue
                    if old_ln in old_docstrings or not _is_code(old_text_lines, old_ln):
                        # Executable new line replacing comment or docstring
                        old_covered = False
                    else:
                        old_covered = (old_ln in file_covered or old_ln in file_imports)

                    if not old_covered:
                        gap_lines.add(new_ln)
                        sym_name = _enclosing_sym(facts, path, new_ln)
                        if sym_name:
                            gap_symbols.add(sym_name)

                # 2) Remaining added lines (nc > oc)
                if nc > oc:
                    if oc > 0:
                        hunk_old_lines = set(range(os_, os_ + oc))
                        hunk_covered = bool(hunk_old_lines & (file_covered | file_imports))
                    else:
                        # Pure insertion: check the neighbor line just above
                        hunk_covered = (os_ in file_covered or os_ in file_imports)

                    for i in range(paired_count, nc):
                        new_ln = ns + i
                        if new_ln in new_docstrings or not _is_code(new_text_lines, new_ln):
                            continue
                        if not hunk_covered:
                            gap_lines.add(new_ln)
                            sym_name = _enclosing_sym(facts, path, new_ln)
                            if sym_name:
                                gap_symbols.add(sym_name)

        if gap_lines:
            files_out[path] = {
                "lines": sorted(gap_lines),
                "changed_lines": file_changed_count,
                "symbols": sorted(gap_symbols),
            }

    total_gaps = sum(len(info["lines"]) for info in files_out.values())
    gap_files_count = len(files_out)

    if total_changed == 0:
        summary = "no source files changed"
    elif total_gaps == 0:
        summary = "every changed line ran under at least one test"
    else:
        files_word = "1 file" if gap_files_count == 1 else f"{gap_files_count} files"
        summary = f"{total_gaps} of {total_changed} changed lines in {files_word} ran under no test"

    return {"files": files_out, "summary": summary}
