"""Helpers shared by language specs (not a spec itself: modules starting with `_` are not discovered)."""
from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path


def txt(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def string_value(node, src: bytes) -> str | None:
    """The value of a plain string literal node (no interpolation), else None."""
    if node is None:
        return None
    t = txt(node, src)
    if node.type in ("template_string",) and "${" in t:
        return None
    m = re.fullmatch(r"""[rbuRBU]*(['"`]{1,3})(.*)\1""", t, re.S)
    return m.group(2) if m else None


def first_arg(call, src: bytes):
    args = call.child_by_field_name("arguments")
    if args is None:
        return None
    named = [c for c in args.named_children if "comment" not in c.type]
    return named[0] if named else None


def callee_name(call, src: bytes) -> str:
    """Last identifier of the called function (`a.b.c(...)` -> `c`) and its full text."""
    fn = call.child_by_field_name("function") or call.child_by_field_name("name")
    return txt(fn, src) if fn is not None else ""


def rel_join(from_file: str, spec: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(from_file), spec))


def same_dir(files: set[str], f: str, suffix: tuple[str, ...]) -> list[str]:
    d = posixpath.dirname(f)
    return sorted(x for x in files if posixpath.dirname(x) == d and x != f and x.endswith(suffix))


def load_jsonc(path: Path) -> dict:
    """JSON with comments and trailing commas (tsconfig.json)."""
    try:
        s = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    s = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", s, flags=re.S)
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    try:
        v = json.loads(s)
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}


def leading_insert(body, src: bytes, stmt: str) -> tuple[int, int, str] | None:
    """Insert `stmt` right after the opening brace of a block."""
    if body is None or not body.children or body.children[0].type != "{":
        return None
    at = body.children[0].end_byte
    return at, at, f" {stmt} "
