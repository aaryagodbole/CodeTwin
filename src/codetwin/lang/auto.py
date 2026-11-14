"""A spec for any language that has a tree-sitter grammar but no spec file, built from the repository itself.

Used when a repository contains a language CodeTwin has no `specs/<name>.py` for (Lua, Elixir, Dart, Scala,
Haskell, Zig, ...). Everything is generic and conservative:

- functions: syntax nodes whose type names a function, method or procedure definition;
- dependencies: string or path-like operands of nodes whose type names an import, include, require or use,
  resolved relative to the file or by path suffix against the repository's files (unique matches only);
- tests: the usual naming conventions (`*_test.*`, `test_*.*`, `*.spec.*`, `tests/`, `spec/`, ...).

There is no test-runner preset; with `[runner] test_command` the language gets runtime evidence like any
other, without it CodeTwin works on static evidence and says so in every decision.
"""
from __future__ import annotations

import posixpath
import re
from pathlib import Path

from .base import SAMPLE_DIRS, SKIP_DIRS
from .spec import Spec

TEST_GLOBS = ["*_test.*", "test_*.*", "*.test.*", "*.spec.*", "*_spec.*", "*Test.*", "*Tests.*", "*Spec.*",
              "**/test/**/*.*", "**/tests/**/*.*", "**/spec/**/*.*", "**/__tests__/**/*.*"]
FUNC = re.compile(r"(^|_)(function|method|procedure|subroutine|func|fn|def|lambda|closure)(_|$)")
FUNC_SHAPE = re.compile(r"(definition|declaration|item|statement|_def|literal|expression|clause)$")
IMPORT = re.compile(r"(import|include|require|use_declaration|using|^use$|^open_statement$)")
NOT_CODE = {"markdown", "markdown_inline", "json", "yaml", "toml", "xml", "html", "css", "scss", "csv", "ini",
            "dockerfile", "gomod", "gosum", "gitcommit", "make", "cmake", "gitignore", "gitattributes", "properties", "requirements", "diff",
            "regex", "comment", "jsdoc", "sql", "graphql", "proto", "latex", "bibtex", "rst", "org", "nix",
            "hcl", "terraform", "bash", "powershell", "batch", "vim", "dot", "mermaid", "svelte", "vue",
            "astro", "twig", "jinja", "embedded_template", "po", "readme", "tsv", "psv", "starlark"}


def _ext_grammars(root: Path, max_files: int = 20000) -> dict[str, tuple[str, int]]:
    """Extension -> (grammar, number of files) for every source-like file of the repository."""
    try:
        from tree_sitter_language_pack import detect_language_from_path
    except ImportError:
        return {}
    counts: dict[str, int] = {}
    stack, seen = [root], 0
    while stack and seen < max_files:
        d = stack.pop()
        try:
            entries = sorted(d.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.is_dir():
                if p.name not in SKIP_DIRS and p.name not in SAMPLE_DIRS and not p.name.startswith("."):
                    stack.append(p)
            elif p.suffix:
                counts[p.suffix] = counts.get(p.suffix, 0) + 1
                seen += 1
    out: dict[str, tuple[str, int]] = {}
    for ext, n in counts.items():
        g = detect_language_from_path("x" + ext)
        if g and g not in NOT_CODE:
            out[ext] = (g, n)
    return out


def detect(root: Path) -> dict[str, list[str]]:
    """Grammar -> file extensions present in the repository."""
    out: dict[str, list[str]] = {}
    for ext, (g, _) in _ext_grammars(root).items():
        out.setdefault(g, []).append(ext)
    return out


LOADERS = {"require", "require_relative", "import", "include", "load", "dofile", "use", "loadfile", "source",
           "include_once", "require_once", "importScripts"}
STRING = re.compile(r"""^[rbu@]*['"`]([^'"`\n]{1,200})['"`]$""")


def _call_import(n, src: bytes) -> list[str] | None:
    """`require("x")`, `import("x")`, `load "x"`: a call of a well-known loader with a literal argument."""
    if n.child_count < 2:
        return None
    head = src[n.children[0].start_byte:n.children[0].end_byte].decode("utf-8", "replace").strip()
    if head.split(".")[-1] not in LOADERS:
        return None
    stack = list(n.children[1:])
    while stack:
        c = stack.pop(0)
        m = STRING.match(src[c.start_byte:c.end_byte].decode("utf-8", "replace").strip())
        if m:
            return [m.group(1)]
        stack.extend(c.children)
    return None


def _imports(n, src: bytes) -> list[str] | None:
    if "call" in n.type:
        return _call_import(n, src)
    if not IMPORT.search(n.type) or n.child_count == 0:
        return None
    got = []
    for c in n.children:
        t = src[c.start_byte:c.end_byte].decode("utf-8", "replace").strip()
        if c.type in ("comment",) or not t or len(t) > 200:
            continue
        m = re.fullmatch(r"""[@<"'`]?([\w./:\\@-]+?)[>"'`]?;?""", t)
        if m and ("." in m.group(1) or "/" in m.group(1) or ":" in m.group(1) or c.is_named) \
                and m.group(1) not in ("import", "include", "require", "use", "using", "from", "as", "open"):
            got.append(m.group(1))
    return got or None


def prepare(idx) -> None:
    by_stem: dict[str, list[str]] = {}
    for f in idx.files:
        by_stem.setdefault(posixpath.splitext(f)[0], []).append(f)
    idx.data["by_stem"] = by_stem


def resolve(spec: str, from_file: str, idx) -> list[str]:
    s = spec.replace("\\", "/").replace("::", "/").strip("/")
    by_stem = idx.data["by_stem"]
    if spec.startswith("."):                               # relative path
        p = posixpath.normpath(posixpath.join(posixpath.dirname(from_file), s))
        if p in idx.files:
            return [p]
        hit = by_stem.get(posixpath.splitext(p)[0]) or by_stem.get(p) or by_stem.get(posixpath.join(p, "index"))
        return sorted(hit)[:1] if hit else []
    path = s if "/" in s else s.replace(".", "/")          # dotted module names: a.b.c -> a/b/c
    cands = [st for st in by_stem if st == path or st.endswith("/" + path)]
    if len(cands) == 1:
        return sorted(by_stem[cands[0]])[:1]
    return []


def spec_for(grammar: str, extensions: list[str]) -> Spec:
    return Spec(name=grammar, grammars={e: grammar for e in extensions}, test_globs=list(TEST_GLOBS),
                function_types=set(), decl_types=set(), imports=_imports, prepare=prepare, resolve=resolve,
                auto=True)


def is_function(node_type: str) -> bool:
    return bool(FUNC.search(node_type) and FUNC_SHAPE.search(node_type))
