"""Symbol-level impact: which tests execute a function or class, which code refers to it, and what is unknown.

Language-neutral: symbols and their line spans come from the language adapter (`FileFacts.symbols`), tests
from the recorded per-test line coverage, and callers from the dependency graph plus a whole-word search for the
symbol's name in the files that depend on the symbol's file. Name search is evidence of a *possible* call
(`static-name`), not proof; anything the analysis cannot follow is listed in `unknowns`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..evidence.model import EvidenceType, FileDiff, FileFacts, TestRun
from .impact import build_graph, file_deps, impact_of

STATIC_NAME = "static-name"      # the symbol's name appears in a file that depends on the symbol's file


@dataclass
class Symbol:
    name: str                    # qualified, e.g. "Parser.parse"
    kind: str                    # function, method or class
    file: str
    start: int
    end: int

    @property
    def short(self) -> str:
        return self.name.rsplit(".", 1)[-1]

    def to_dict(self) -> dict:
        return {"name": self.name, "kind": self.kind, "file": self.file, "start": self.start, "end": self.end}


@dataclass
class SymbolImpact:
    symbol: Symbol
    tests: dict[str, set[str]] = field(default_factory=dict)        # test file -> evidence types
    callers: list[dict] = field(default_factory=list)               # {file, line, symbol}
    unknowns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"symbol": self.symbol.to_dict(),
                "tests": {t: sorted(v) for t, v in sorted(self.tests.items())},
                "callers": self.callers, "unknowns": self.unknowns,
                "summary": f"{self.symbol.name}: used by {len({c['file'] for c in self.callers})} files, "
                           f"{len(self.tests)} tests, {len(self.unknowns)} unknown"}


def symbols_of(facts: dict[str, FileFacts], path: str) -> list[Symbol]:
    return [Symbol(n, k, path, a, b) for n, k, a, b in (facts[path].symbols if path in facts else [])]


def base_span(base_facts: dict[str, FileFacts], sym: Symbol, path: str | None = None) -> tuple[int, int] | None:
    """Lines of `sym` in the recorded commit's snapshot (where the recorded coverage line numbers apply), found by
    file and qualified name; the nearest one if the name occurs more than once. None if it did not exist then."""
    cands = [s for s in symbols_of(base_facts, path or sym.file) if s.name == sym.name and s.kind == sym.kind]
    if not cands:
        return None
    best = min(cands, key=lambda s: abs(s.start - sym.start))
    return best.start, best.end


PARSE_MARKERS = ("unparsed", "parse-error")


def parse_target(target: str) -> tuple[str, str | None]:
    """`path:Name`, `path:Class.method` or `path:42` (line); a plain path means the whole file."""
    if ":" in target and not re.match(r"^[A-Za-z]:[\\/]", target):
        path, _, sym = target.rpartition(":")
        return path, sym or None
    return target, None


def find(facts: dict[str, FileFacts], path: str, query: str) -> list[Symbol]:
    """Symbols of `path` matching a qualified name, a short name, or (for a number) the innermost one at that line."""
    syms = symbols_of(facts, path)
    if query.isdigit():
        ln = int(query)
        at = [s for s in syms if s.start <= ln <= s.end]
        return [min(at, key=lambda s: s.end - s.start)] if at else []
    exact = [s for s in syms if s.name == query]
    return exact or [s for s in syms if s.short == query or s.name.endswith("." + query)]


def enclosing(facts: dict[str, FileFacts], path: str, ln: int) -> str | None:
    at = [s for s in symbols_of(facts, path) if s.start <= ln <= s.end]
    return min(at, key=lambda s: s.end - s.start).name if at else None


def _read(root: Path, path: str) -> list[str]:
    try:
        return (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def callers_of(root: Path, facts: dict[str, FileFacts], sym: Symbol) -> list[dict]:
    """Lines in the symbol's own file (outside its body) and in files that depend on it that mention its name."""
    deps = file_deps(facts)
    files = [sym.file] + sorted(f for f, d in deps.items() if sym.file in d and f != sym.file)
    pat = re.compile(rf"(?<![\w$]){re.escape(sym.short)}(?![\w$])")
    out = []
    for f in files:
        for i, text in enumerate(_read(root, f), start=1):
            if f == sym.file and sym.start <= i <= sym.end:
                continue
            if pat.search(text):
                out.append({"file": f, "line": i, "symbol": enclosing(facts, f, i)})
    return out


def symbol_impact(root: Path, facts: dict[str, FileFacts], run: TestRun | None, tests: list[str],
                  sym: Symbol, is_test=lambda f: False, base_facts: dict[str, FileFacts] | None = None) -> SymbolImpact:
    """`base_facts`: static snapshot of the recorded run's commit. Recorded coverage uses that commit's line numbers,
    so the symbol's span is taken from it; the working tree's span is right only if no line moved."""
    imp = SymbolImpact(sym)
    span = set(range(sym.start, sym.end + 1))
    new_symbol = False
    if run is not None and base_facts:
        bs = base_span(base_facts, sym)
        if bs is None:
            new_symbol = True
            imp.unknowns.append(f"{sym.name} did not exist at the recorded commit: no recorded test has executed it")
        else:
            span = set(range(bs[0], bs[1] + 1))
    elif run is not None:
        imp.unknowns.append("no static snapshot of the recorded commit: its coverage is matched by the current line "
                            "numbers, which are wrong if lines moved (run `codetwin record` again)")
    if run is None:
        imp.unknowns.append("no recorded test run: which tests execute this symbol is unknown (run `codetwin record`)")
    elif not new_symbol:
        for t, files in run.covered.items():
            if span & set(files.get(sym.file, [])):
                imp.tests.setdefault(t, set()).add(EvidenceType.RUNTIME.value)
        if not imp.tests:
            imp.unknowns.append(f"no test executes {sym.name} ({sym.file}:{sym.start}-{sym.end}): test gap")
    imp.callers = [c for c in callers_of(root, facts, sym) if not is_test(c["file"])]
    test_refs = {c["file"] for c in callers_of(root, facts, sym) if is_test(c["file"])}
    for t in test_refs:
        imp.tests.setdefault(t, set()).add(STATIC_NAME)
    caller_files = sorted({c["file"] for c in imp.callers} - {sym.file})
    if caller_files:
        reach = impact_of(build_graph(facts, run), caller_files, tests)
        for t, ev in reach.tests.items():
            imp.tests.setdefault(t, set()).update({f"via-caller:{e}" for e in ev})
    f = facts.get(sym.file)
    if f is not None and "unparsed" in f.dynamic:
        imp.unknowns.append(f"{sym.file} could not be parsed: callers and symbols in it are unknown")
    elif f is not None and "parse-error" in f.dynamic:
        imp.unknowns.append(f"{sym.file} has syntax errors: it was parsed only in part, so symbols and callers in "
                            "it may be missing")
    deps = file_deps(facts)
    dyn = sorted(g for g, d in deps.items() if sym.file in d and facts[g].dynamic and g not in caller_files)
    for g in dyn[:20]:
        imp.unknowns.append(f"{g} depends on {sym.file} and uses dynamic calls ({', '.join(facts[g].dynamic)}): "
                            f"it may call {sym.short} without naming it")
    return imp


def changed_symbols(facts: dict[str, FileFacts], diff: dict[str, FileDiff], run: TestRun | None,
                    is_source=lambda f: True, base_facts: dict[str, FileFacts] | None = None) -> list[dict]:
    """Symbols of the working tree whose lines changed, with the number of tests that executed them before
    (counted on the symbol's lines at the recorded commit, from `base_facts`; 0 for a symbol that is new)."""
    out: list[dict] = []
    for path, d in sorted(diff.items()):
        if not is_source(path) or d.status == "D":
            continue
        lines = set(d.new)
        for sym in symbols_of(facts, path):
            span = set(range(sym.start, sym.end + 1))
            if lines & span:
                old = d.old_path or path
                if base_facts:
                    bs = base_span(base_facts, sym, old)
                    before = set(range(bs[0], bs[1] + 1)) if bs else set()
                else:
                    before = span
                n = 0 if run is None else sum(1 for files in run.covered.values() if before & set(files.get(old, [])))
                out.append({**sym.to_dict(), "tests_before": n})
    # keep the innermost changed symbols: a class whose only changed lines are inside a changed method is noise
    inner = []
    for s in out:
        if not any(o is not s and o["file"] == s["file"] and s["start"] <= o["start"] and o["end"] <= s["end"]
                   and (o["start"], o["end"]) != (s["start"], s["end"]) for o in out):
            inner.append(s)
    return inner
