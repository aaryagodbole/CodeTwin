"""Semantic no-op detection for Python changes.

A change to a source file is
  * "noop"        if the abstract syntax trees of the old and new file are identical once docstrings
                  are removed (comments and formatting do not reach the AST at all);
  * "annotation"  if they become identical once, in addition, the annotations of function arguments and
                  return values are removed (annotated assignments are kept, because dataclasses and
                  similar libraries read them at run time);
  * "semantic"    otherwise; "unparsable" if either version does not parse.

A change is a no-op as a whole only if every changed source file is a no-op and no file was added or
deleted. Annotation-only changes are reported separately and are NOT treated as safe to skip: libraries
such as pydantic, typing.get_type_hints or functools.singledispatch read annotations at run time.
"""
import ast
import subprocess

DOC_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


class _StripDocstrings(ast.NodeTransformer):
    def generic_visit(self, node):
        super().generic_visit(node)
        if isinstance(node, DOC_NODES):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
        return node


class _StripAnnotations(ast.NodeTransformer):
    def visit_arg(self, node):
        node.annotation = None
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.returns = None
        return node

    visit_AsyncFunctionDef = visit_FunctionDef


def _norm(src, strip_annotations=False):
    tree = ast.parse(src)
    tree = _StripDocstrings().visit(tree)
    if strip_annotations:
        tree = _StripAnnotations().visit(tree)
    return ast.dump(tree, include_attributes=False)


def classify_source(old_src, new_src):
    try:
        if _norm(old_src) == _norm(new_src):
            return "noop"
        if _norm(old_src, True) == _norm(new_src, True):
            return "annotation"
        return "semantic"
    except (SyntaxError, ValueError, RecursionError):
        return "unparsable"


def git_show(repo, rev, path):
    r = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def classify_change(repo, parent, sha, diff, is_src):
    """diff: {path: {"status": A|M|D|R, "old_path": ...}} as stored by the collector."""
    files = {}
    for f, d in diff.items():
        if not is_src(f):
            continue
        st = d.get("status")
        if st in ("A", "D"):
            files[f] = "added" if st == "A" else "deleted"
            continue
        old = git_show(repo, parent, d.get("old_path", f))
        new = git_show(repo, sha, f)
        if old is None or new is None:
            files[f] = "unavailable"
            continue
        files[f] = classify_source(old, new)
    kinds = set(files.values())
    if not files:
        kind = "no-source"
    elif kinds == {"noop"}:
        kind = "noop"
    elif kinds <= {"noop", "annotation"}:
        kind = "annotation"
    else:
        kind = "semantic"
    return kind, files
