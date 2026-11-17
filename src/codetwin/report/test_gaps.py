"""Section: changed lines that ran under no test before the change (test gaps)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..evidence.diff import git
from ..graph.symbols import changed_symbols, symbols_of

NAME = "test_gaps"


def _read_old_lines(repo: Path, base: str, old_path: str) -> list[str]:
    try:
        return git(repo, "show", f"{base}:{old_path}").splitlines()
    except Exception:
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

    for path, d in sorted(ctx.diff.items()):
        if not ctx.is_source(path) or d.status == "D":
            continue

        old_path = d.old_path or path
        new_text_lines = _read_working_lines(repo, path)
        old_text_lines = _read_old_lines(repo, ctx.base, old_path) if ctx.base else []

        gap_lines: set[int] = set()
        gap_symbols: set[str] = set()

        if d.status == "A":
            # New file: all non-empty, non-comment lines in d.new are gaps
            for ln in d.new:
                if _is_code(new_text_lines, ln):
                    gap_lines.add(ln)
            for s in syms:
                if s.get("file") == path:
                    gap_symbols.add(s["name"])
        else:
            # Rule 1: changed lines inside untested symbols
            file_untested = [s for s in untested_syms if s.get("file") == path]
            for s in file_untested:
                s_start, s_end = s["start"], s["end"]
                for ln in d.new:
                    if s_start <= ln <= s_end and _is_code(new_text_lines, ln):
                        gap_lines.add(ln)
                        gap_symbols.add(s["name"])

            # Rule 2: Edited lines inside tested functions / hunks
            file_covered = covered_lines.get(old_path, set())
            file_imports = import_lines.get(old_path, set())

            for (os_, oc, ns, nc) in getattr(d, "hunks", []):
                if oc == nc and oc > 0:
                    for i in range(oc):
                        old_ln = os_ + i
                        new_ln = ns + i

                        # Skip comment or blank lines in either old or new version
                        if not _is_code(old_text_lines, old_ln):
                            continue
                        if not _is_code(new_text_lines, new_ln):
                            continue

                        # If not covered by any test and not run at import time
                        if old_ln not in file_covered and old_ln not in file_imports:
                            gap_lines.add(new_ln)
                            sym_name = _enclosing_sym(facts, path, new_ln)
                            if sym_name:
                                gap_symbols.add(sym_name)

        if gap_lines:
            files_out[path] = {
                "lines": sorted(gap_lines),
                "changed_lines": len(d.new),
                "symbols": sorted(gap_symbols),
            }

    total_changed = sum(len(d.new) for f, d in ctx.diff.items() if ctx.is_source(f) and d.status != "D")
    total_gaps = sum(len(info["lines"]) for info in files_out.values())
    gap_files_count = len(files_out)

    if total_changed == 0:
        summary = "no source files changed"
    else:
        files_word = "1 file" if gap_files_count == 1 else f"{gap_files_count} files"
        summary = f"{total_gaps} of {total_changed} changed lines in {files_word} ran under no test"

    return {"files": files_out, "summary": summary}
