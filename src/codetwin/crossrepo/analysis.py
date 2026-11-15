"""Cross-repository impact of a change (see the package docstring)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import config as cfgmod
from .. import lang as langmod
from ..graph.impact import build_graph, impact_of
from . import packages as pkgmod

USES_SYMBOL = "uses-changed-symbol"
IMPORTS = "imports-package"


@dataclass
class RepoImpact:
    name: str
    path: str
    language: str | None = None
    packages: list[str] = field(default_factory=list)
    consumers: list[dict] = field(default_factory=list)       # {file, link, symbols, lines}
    tests: dict[str, set[str]] = field(default_factory=dict)  # test file -> evidence
    unknowns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        strong = sum(1 for c in self.consumers if c["link"] == USES_SYMBOL)
        return {"name": self.name, "path": self.path, "language": self.language, "packages": self.packages,
                "consumers": self.consumers, "tests": {t: sorted(v) for t, v in sorted(self.tests.items())},
                "unknowns": self.unknowns,
                "summary": f"{self.name}: {strong} files use a changed symbol, "
                           f"{len(self.consumers) - strong} more import the package, {len(self.tests)} tests, "
                           f"{len(self.unknowns)} unknown"}


IMPORT_LINE = re.compile(r"^\s*(import|from|use|using|require|include|#include|@import|extern\s+crate|load)\b"
                         r"|\brequire\s*\(|\bimport\s*\(")
TOKEN = re.compile(r"[\w@$./:\\-]+")


def import_lines(lines: list[str], packages: list[str]) -> list[str]:
    """Import strings naming one of `packages` on import-like lines (any language). Adapters may keep only a
    project's own imports in `FileFacts.imports`, so a dependent's imports of this repository are read here."""
    out = []
    for line in lines[:400]:
        if not IMPORT_LINE.search(line):
            continue
        for tok in TOKEN.findall(line.replace("'", " ").replace('"', " ").replace("`", " ")):
            tok = tok.rstrip(";,.")
            if any(pkgmod.matches(tok, p) for p in packages):
                out.append(tok)
    return out


def declared(cfg) -> list[dict]:
    repos = cfg.raw.get("repos", [])
    return [r for r in repos if isinstance(r, dict) and r.get("path")] if isinstance(repos, list) else []


def own_packages(cfg) -> list[str]:
    override = cfg.section("crossrepo")
    if isinstance(override, dict) and override.get("packages"):
        return list(override["packages"])
    return pkgmod.detect(cfg.root, cfg.packages)


def _dependent_config(path: Path):
    try:
        return cfgmod.load(path)
    except FileNotFoundError:
        return cfgmod.Config(root=path.resolve(), language="auto")


def _recorded_run(dcfg):
    if not dcfg.db_path.exists():
        return None
    from ..store.db import Store
    with Store(dcfg.db_path) as st:
        sha = st.latest_run_sha()
        return st.get_run(sha) if sha else None


def analyse(cfg, changed_symbols: list[str], changed_files: list[str]) -> list[RepoImpact]:
    """Impact of a change in this repository on every declared dependent. `changed_symbols` are short names of
    changed functions, methods and classes; `changed_files` the changed source files (for the summary)."""
    out: list[RepoImpact] = []
    mine = own_packages(cfg)
    names = sorted({s.rsplit(".", 1)[-1] for s in changed_symbols if s})
    sym_rx = re.compile(r"(?<![\w$])(" + "|".join(map(re.escape, names)) + r")(?![\w$])") if names else None
    for r in declared(cfg):
        path = (cfg.root / str(r["path"])).resolve()
        ri = RepoImpact(name=str(r.get("name") or path.name), path=str(path))
        pk = list(r.get("packages") or mine)
        ri.packages = pk
        if not path.exists():
            ri.unknowns.append(f"repository {ri.name} not found at {path}: its consumers are unknown")
            out.append(ri)
            continue
        if not pk:
            ri.unknowns.append(f"no package name known for this repository; set [crossrepo] packages or "
                               f"packages in the [[repos]] entry of {ri.name}")
            out.append(ri)
            continue
        dcfg = _dependent_config(path)
        try:
            adapter = langmod.get(dcfg)
        except Exception as e:  # noqa: BLE001 - an unsupported dependent is an unknown, not a crash
            ri.unknowns.append(f"{ri.name}: language not supported ({e}); its consumers are unknown")
            out.append(ri)
            continue
        ri.language = getattr(adapter, "name", None) or dcfg.language
        facts = adapter.facts()
        tests = adapter.list_tests()
        for f, fx in sorted(facts.items()):
            text = (path / f).read_text(encoding="utf-8", errors="replace").splitlines() if (path / f).exists() else []
            hit = [i for i in fx.imports if any(pkgmod.matches(i, p) for p in pk)] + import_lines(text, pk)
            if not hit:
                continue
            used: dict[str, list[int]] = {}
            if sym_rx:
                for n, line in enumerate(text, start=1):
                    for m in sym_rx.finditer(line):
                        used.setdefault(m.group(1), []).append(n)
            ri.consumers.append({"file": f, "link": USES_SYMBOL if used else IMPORTS, "imports": sorted(set(hit)),
                                 "symbols": sorted(used), "lines": sorted({x for v in used.values() for x in v})[:50],
                                 "is_test": adapter.is_test(f)})
        dyn = sorted(f for f, fx in facts.items() if fx.dynamic and any(d != "parse-error" for d in fx.dynamic))
        if dyn:
            ri.unknowns.append(f"{len(dyn)} files in {ri.name} use dynamic imports or calls "
                               f"(e.g. {', '.join(dyn[:3])}): they may use this repository without importing it")
        if not ri.consumers:
            out.append(ri)
            continue
        cons = [c for c in ri.consumers if not c["is_test"]]
        for c in ri.consumers:
            if c["is_test"]:
                ri.tests.setdefault(c["file"], set()).add(f"direct:{c['link']}")
        run = _recorded_run(dcfg)
        if run is None:
            ri.unknowns.append(f"no recorded run in {ri.name}: tests found through its static import graph only "
                               f"(run `codetwin record` there for runtime evidence)")
        reach = impact_of(build_graph(facts, run), [c["file"] for c in cons], tests)
        for t, ev in reach.tests.items():
            ri.tests.setdefault(t, set()).update(ev)
        covered = {f for files in run.covered.values() for f in files} if run is not None else set()
        for c in cons:
            if run is not None and c["link"] == USES_SYMBOL and c["file"] not in covered:
                ri.unknowns.append(f"{ri.name}:{c['file']} uses {', '.join(c['symbols'])} but no recorded test "
                                   "executes it: test gap in the dependent")
        out.append(ri)
    return out


def for_change(cfg, facts: dict, diff: dict, is_source) -> dict:
    """Cross-repository impact of a diff of this repository, as the JSON shape used by the CLI, report and MCP."""
    from ..graph.symbols import changed_symbols
    if not declared(cfg):
        return {"repos": [], "summary": "no connected repositories ([[repos]] in .codetwin.toml)"}
    syms = changed_symbols(facts, diff, None, is_source)
    files = sorted(f for f in diff if is_source(f))
    repos = [r.to_dict() for r in analyse(cfg, [s["name"] for s in syms], files)]
    n_files = sum(len(r["consumers"]) for r in repos)
    n_tests = sum(len(r["tests"]) for r in repos)
    n_unk = sum(len(r["unknowns"]) for r in repos)
    return {"changed_symbols": [s["name"] for s in syms], "packages": own_packages(cfg), "repos": repos,
            "summary": f"{len(repos)} connected repositories: {n_files} consumer files, {n_tests} tests, {n_unk} unknown"}
