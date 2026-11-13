"""Semantic no-op changes: edits that cannot change what a Python program does.

A changed source file is a *no-op* when the abstract syntax trees of its old and new versions are
identical once docstrings are removed (comments and formatting never reach the AST). It is
*annotation-only* when they become identical once argument and return annotations are also removed.
Annotation-only changes are reported but NOT treated as safe: pydantic, dataclasses-style libraries,
typing.get_type_hints and functools.singledispatch read annotations at run time.

In the study (paper, Section 7), 41 of 332 history test changes were no-ops and none of them changed
the outcome of any test file.
"""
from __future__ import annotations

import ast
import subprocess
from collections.abc import Callable
from pathlib import Path

from .model import FileDiff

_DOC_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


class _StripDocstrings(ast.NodeTransformer):
    def generic_visit(self, node: ast.AST) -> ast.AST:
        super().generic_visit(node)
        body = getattr(node, "body", None)
        if isinstance(node, _DOC_NODES) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
        return node


class _StripAnnotations(ast.NodeTransformer):
    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.annotation = None
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.returns = None
        return node

    visit_AsyncFunctionDef = visit_FunctionDef


def _norm(src: str, strip_annotations: bool = False) -> str:
    tree = _StripDocstrings().visit(ast.parse(src))
    if strip_annotations:
        tree = _StripAnnotations().visit(tree)
    return ast.dump(tree, include_attributes=False)


def classify_source(old_src: str, new_src: str) -> str:
    """'noop', 'annotation', 'semantic' or 'unparsable'."""
    try:
        if _norm(old_src) == _norm(new_src):
            return "noop"
        if _norm(old_src, True) == _norm(new_src, True):
            return "annotation"
        return "semantic"
    except (SyntaxError, ValueError, RecursionError):
        return "unparsable"


def _show(root: Path, rev: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=root, capture_output=True, check=False)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def classify_change(root: str | Path, base: str, diff: dict[str, FileDiff],
                    is_source: Callable[[str], bool]) -> tuple[str, dict[str, str]]:
    """Kind of the whole change ('noop', 'annotation', 'semantic' or 'no-source') and per-file kinds,
    comparing `base` with the working tree."""
    root = Path(root)
    files: dict[str, str] = {}
    for f, d in diff.items():
        if not is_source(f):
            continue
        if d.status in ("A", "D"):
            files[f] = "added" if d.status == "A" else "deleted"
            continue
        old = _show(root, base, d.old_path or f)
        p = root / f
        new = p.read_text(encoding="utf-8", errors="replace") if p.exists() else None
        files[f] = "unavailable" if old is None or new is None else classify_source(old, new)
    kinds = set(files.values())
    if not files:
        return "no-source", files
    if kinds == {"noop"}:
        return "noop", files
    if kinds <= {"noop", "annotation"}:
        return "annotation", files
    return "semantic", files
