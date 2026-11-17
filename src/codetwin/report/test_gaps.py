"""Section: changed lines that ran under no test before the change (test gaps).

Two rules identify test gaps (reported as 1-based line numbers in the working tree):
1. New or untested functions: changed lines inside functions, methods or classes
   with `tests_before == 0` (via `codetwin.graph.symbols.changed_symbols`).
2. Edited lines inside tested functions: lines from diff hunks where the
   corresponding old line was neither covered by any test (`ctx.prev.covered`)
   nor executed at import time (`ctx.prev.import_lines`). For unequal-length
   additions (`nc > oc`), added lines are gaps unless all of the hunk's old lines
   were covered or imported. A pure insertion takes the coverage of the nearest
   old code line, above or below, with the same indentation as the inserted code,
   within the same block. The body of a block opened by an added line (`if x:`)
   has no execution evidence of its own and is always a gap.

Skipped lines (never reported as gaps):
- Import-time lines: `def` headers and module-level constants executed at import.
- Comments and blank lines: lines that are empty or start with `#`.
- Docstrings: docstring line spans without executable statements (parsed via `ast`).

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
When no gaps exist, summary is "no test gaps found" (or "no source files changed" if the diff has no source file).
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
    doc_lines: set[int] = set()
    other_stmt_lines: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            doc_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        elif isinstance(node, ast.stmt):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.If,
                    ast.For,
                    ast.While,
                    ast.With,
                    ast.Try,
                ),
            ):
                other_stmt_lines.add(node.lineno)
            else:
                other_stmt_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return doc_lines - other_stmt_lines


def _base_line_for_new(hunks: list[tuple[int, int, int, int]], new_ln: int) -> int | None:
    for os_, oc, ns, nc in hunks:
        if ns <= new_ln < ns + min(oc, nc):
            return os_ + (new_ln - ns)
    return None


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


def _indent(s: str) -> int:
    return len(s) - len(s.lstrip())


def _insertion_anchor(old_lines: list[str], new_lines: list[str], os_: int, ns: int, nc: int) -> int:
    """Old line whose coverage stands for a pure insertion after old line `os_` (git `-os_,0 +ns,nc`).

    The inserted code runs whenever the old code at the same indentation runs. So take the nearest old code
    line above or below the insertion with the same indentation as the first inserted code line, preferring
    the one above. Example: a line inserted after an `if` block, at function level, is anchored to the
    function-level line below it, not to the last line inside the (maybe untested) `if` branch."""
    new_code = [new_lines[ln - 1] for ln in range(ns, ns + nc) if ln <= len(new_lines) and _is_code(new_lines, ln)]
    if not new_code or not old_lines:
        return os_
    want = _indent(new_code[0])

    def nearest(lines: range) -> int:
        # Skip deeper lines (bodies of blocks at this level); stop when the code leaves this block.
        for ln in lines:
            if not _is_code(old_lines, ln):
                continue
            ind = _indent(old_lines[ln - 1])
            if ind == want:
                return ln
            if ind < want:
                return 0
        return 0

    found = nearest(range(os_, 0, -1)) or nearest(range(os_ + 1, len(old_lines) + 1))
    if found:
        return found
    return next((ln for ln in range(os_, 0, -1) if _is_code(old_lines, ln)), 0) or os_


def _new_block_bodies(lines: list[str], start: int, end: int) -> set[int]:
    """Lines in [start, end] that are the body of a block opened by an added line (`if x:` ... ). Such a body
    has no execution evidence of its own, so it never inherits the coverage of the code around it."""
    out: set[int] = set()
    opener: int | None = None   # indentation of the innermost added line that opens a block
    for ln in range(start, min(end, len(lines)) + 1):
        if not _is_code(lines, ln):
            continue
        ind = _indent(lines[ln - 1])
        if opener is not None and ind > opener:
            out.add(ln)
            continue
        opener = ind if lines[ln - 1].split("#", 1)[0].rstrip().endswith(":") else None
    return out


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
    source_files_changed = 0

    for path, d in sorted(ctx.diff.items()):
        if not ctx.is_source(path):
            continue
        source_files_changed += 1
        if d.status == "D":
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
                    ):
                        base_ln = _base_line_for_new(d.hunks, ln)
                        if base_ln is not None and base_ln in file_imports:
                            continue
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
                        # In mixed-coverage hunks, additions are only covered if all replaced
                        # old lines were covered or imported.
                        hunk_covered = all(
                            ln in file_covered or ln in file_imports for ln in hunk_old_lines
                        )
                    else:
                        # Pure insertion: the neighbouring old code line at the same indentation
                        anchor = _insertion_anchor(old_text_lines, new_text_lines, os_, ns, nc)
                        hunk_covered = (anchor in file_covered or anchor in file_imports)

                    bodies = _new_block_bodies(new_text_lines, ns + paired_count, ns + nc - 1)
                    for i in range(paired_count, nc):
                        new_ln = ns + i
                        if new_ln in new_docstrings or not _is_code(new_text_lines, new_ln):
                            continue
                        if not hunk_covered or new_ln in bodies:
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

    if source_files_changed == 0:
        summary = "no source files changed"
    elif total_gaps == 0:
        summary = "no test gaps found"
    else:
        files_word = "1 file" if gap_files_count == 1 else f"{gap_files_count} files"
        summary = f"{total_gaps} of {total_changed} changed lines in {files_word} ran under no test"

    return {"files": files_out, "summary": summary}
