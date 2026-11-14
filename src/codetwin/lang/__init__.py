"""Pluggable language support.

`get(cfg)` returns the adapter for a project: Python (built in, no extra dependency) or the generic tree-sitter
adapter configured by a spec from `lang/specs/` (one file per language, discovered automatically). The
language comes from `[project] language` in `.codetwin.toml`; "auto" or a missing value is detected from the
files in the repository.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..plugins import discover
from .base import SAMPLE_DIRS, Language, glob_match, repo_files
from .spec import Spec

if TYPE_CHECKING:
    from ..config import Config

ALIASES = {"js": "javascript", "ts": "javascript", "typescript": "javascript", "node": "javascript",
           "golang": "go", "c": "cpp", "c++": "cpp", "cs": "csharp", "c#": "csharp", "kt": "kotlin", "rb": "ruby",
           "py": "python"}


def load_specs() -> dict[str, Spec]:
    out = {}
    for mod in discover("codetwin.lang.specs"):
        spec = getattr(mod, "SPEC", None)
        if isinstance(spec, Spec):
            out[spec.name] = spec
    return out


def names() -> list[str]:
    return ["python", *sorted(load_specs())]


PY_MARKERS = ["pyproject.toml", "setup.py", "setup.cfg"]


def _candidates(root: Path) -> dict[str, tuple[tuple[str, ...], list[str], list[str]]]:
    """Every language with files in the repository: name -> (extensions, markers, test globs)."""
    from . import auto
    out: dict[str, tuple[tuple[str, ...], list[str], list[str]]] = {"python": ((".py",), PY_MARKERS, ["test_*.py", "*_test.py", "**/tests/**/*.py", "**/test/**/*.py"])}
    known_exts = {".py"}
    for name, sp in load_specs().items():
        out[name] = (tuple(sp.grammars), sp.markers, sp.test_globs)
        known_exts |= set(sp.grammars)
    for grammar, exts in auto.detect(root).items():       # languages without a spec file
        rest = tuple(e for e in exts if e not in known_exts)
        if rest and grammar not in out:
            out[grammar] = (rest, [], auto.TEST_GLOBS)
    return out


def _census(root: Path) -> dict[str, tuple[int, int, bool]]:
    """name -> (source files, test files, build marker present)."""
    out = {}
    for name, (exts, markers, globs) in _candidates(root).items():
        files = repo_files(root, exts, skip=SAMPLE_DIRS)
        if not files:
            continue
        tests = sum(glob_match(f, globs) for f in files)
        out[name] = (len(files) - tests, tests, any((root / m).exists() for m in markers if "*" not in m))
    return out


def detect_all(root: str | Path) -> list[str]:
    """Languages CodeTwin should handle in this repository, most files first. A language counts when it has
    both source and test files (a few helper scripts in another language do not make a repository
    multi-language); if none has tests, the language with the most files (preferring one with a build file)."""
    census = _census(Path(root))
    tested = [n for n, (src, tst, _) in census.items() if src and tst]
    if tested:
        return sorted(tested, key=lambda n: (-(census[n][0] + census[n][1]), n))
    if not census:
        return ["python"]
    return [max(census, key=lambda n: (census[n][2], census[n][0] + census[n][1], n == "python"))]


def detect(root: str | Path) -> str:
    """The main language of a repository (the first of `detect_all`)."""
    return detect_all(root)[0]


def sub_config(cfg: Config, name: str) -> Config:
    """The configuration of one language in a multi-language repository: its `[lang.<name>]` table
    (source_dirs, tests_dir, src_root, packages, runner, language) over the project's defaults."""
    from dataclasses import replace
    t = cfg.raw.get("lang", {}).get(name, {}) if isinstance(cfg.raw.get("lang"), dict) else {}
    raw = dict(cfg.raw)
    for key in ("runner", "language"):
        if key in t:
            raw[key] = t[key]
        elif len(cfg.raw.get("lang", {})) > 0:
            raw.pop(key, None)
    return replace(cfg, language=name, src_root=t.get("src_root", cfg.src_root),
                   packages=list(t.get("packages", cfg.packages if name == "python" else [])),
                   source_dirs=list(t.get("source_dirs", cfg.source_dirs)), tests_dir=t.get("tests_dir", cfg.tests_dir),
                   raw=raw)


def adapter(cfg: Config, name: str) -> Language:
    name = ALIASES.get(name.lower(), name.lower())
    if name == "python":
        from .python import Python
        return Python(cfg)
    from .generic import Generic
    all_specs = load_specs()
    if name in all_specs:
        return Generic(cfg, all_specs[name])
    custom = custom_spec(name, cfg.section("language"))
    if custom is not None:
        return Generic(cfg, custom)
    from . import auto
    exts = auto.detect(cfg.root).get(name)
    if exts:
        return Generic(cfg, auto.spec_for(name, exts))
    raise ValueError(f"unknown language {name!r}: no spec ({', '.join(names())}), no [language] table and no "
                     "files with a tree-sitter grammar of that name in the repository (docs/languages.md)")


def get(cfg: Config) -> Language:
    langs = cfg.raw.get("project", {}).get("languages") if isinstance(cfg.raw.get("project"), dict) else None
    if isinstance(langs, list) and langs:
        names_ = [str(x) for x in langs]
    else:
        name = (cfg.language or "auto").lower()
        if name != "auto":
            names_ = [name]
        elif cfg.packages:
            # configurations written before languages were pluggable list Python packages and no language
            names_ = ["python"]
        else:
            names_ = detect_all(cfg.root)
    if len(names_) == 1:
        return adapter(cfg, names_[0])
    from .multi import Multi
    return Multi(cfg, [adapter(sub_config(cfg, n), n) for n in names_])


def custom_spec(name: str, opts) -> Spec | None:
    """A language without a spec file, described in `.codetwin.toml`:

        [language]
        grammar = "lua"                  # any tree-sitter-language-pack grammar
        extensions = [".lua"]
        test_globs = ["*_spec.lua"]
        function_types = ["function_declaration"]   # optional: enables function-level features

    Without import rules the static graph is empty; selection then rests on coverage, and the decision says
    that no static evidence exists."""
    if not isinstance(opts, dict) or not opts.get("extensions"):
        return None
    grammar = str(opts.get("grammar", name))
    exts = [str(e) for e in opts["extensions"]]
    return Spec(name=name, grammars={e: grammar for e in exts}, test_globs=[str(g) for g in opts.get("test_globs", [])],
                function_types=set(opts.get("function_types", [])), decl_types=set(opts.get("decl_types", [])))
