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
from .base import Language, repo_files
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


def detect(root: str | Path) -> str:
    """Most likely language of a repository: build markers first, then the most common source extension."""
    root = Path(root)
    all_specs = load_specs()
    markers = {"python": ["pyproject.toml", "setup.py", "setup.cfg"]}
    exts: dict[str, tuple[str, ...]] = {"python": (".py",)}
    for name, sp in all_specs.items():
        markers[name], exts[name] = sp.markers, tuple(sp.grammars)
    counts = {name: len(repo_files(root, e)) for name, e in exts.items()}
    # A repository often carries a second build file for tooling (package.json in a Python project), so a
    # marker only makes a language a candidate; among candidates the one with the most source files wins.
    marked = [n for n, ms in markers.items() if any((root / m).exists() for m in ms) and counts[n]]
    pool = marked or [n for n in counts if counts[n]]
    return max(pool, key=lambda n: (counts[n], n == "python")) if pool else "python"


def get(cfg: Config) -> Language:
    name = (cfg.language or "auto").lower()
    name = ALIASES.get(name, name)
    if name == "auto":
        # configurations written before languages were pluggable list Python packages and no language
        name = "python" if cfg.packages else detect(cfg.root)
    if name == "python":
        from .python import Python
        return Python(cfg)
    all_specs = load_specs()
    from .generic import Generic
    if name in all_specs:
        return Generic(cfg, all_specs[name])
    custom = custom_spec(name, cfg.section("language"))
    if custom is None:
        raise ValueError(f"unknown language {cfg.language!r}; built in: {', '.join(names())}. For any other "
                         "language with a tree-sitter grammar, add a [language] table with grammar, extensions and "
                         "test_globs (docs/languages.md)")
    return Generic(cfg, custom)


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
