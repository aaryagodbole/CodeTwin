"""Static facts of Python files: imports, dynamic calls, function spans, import-time statements."""
from __future__ import annotations

import ast
import os
from pathlib import Path

from .model import FileFacts

DYN_CALLS = {"__import__", "eval", "exec", "import_module"}


def analyse_file(path: Path, root: Path, packages: list[str]) -> FileFacts:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return FileFacts(dynamic=["unparsed"])
    mod_parts = os.path.relpath(path, root).replace(os.sep, "/")[:-3].split("/")
    imports: set[str] = set()
    dyn: set[str] = set()
    dyn_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = mod_parts[:-1]
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                name = ".".join(base) + ("." + node.module if node.module else "")
            else:
                name = node.module or ""
            imports.add(name)
            imports.update(name + "." + a.name for a in node.names)
        elif isinstance(node, ast.Call):
            f = node.func
            fname = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            hit = fname if fname in DYN_CALLS else None
            if fname in ("getattr", "setattr", "hasattr") and len(node.args) >= 2 and not isinstance(node.args[1], ast.Constant):
                hit = "getattr-dynamic"
            if hit:
                dyn.add(hit)
                dyn_lines.add(node.lineno)
    defs: list[list[int]] = []
    mod_lines: set[int] = set()

    def visit(body, at_import):
        for i, st in enumerate(body):
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([d.lineno for d in st.decorator_list] + [st.lineno])
                defs.append([start, st.end_lineno, st.body[0].lineno])
                if at_import:
                    for d in st.decorator_list:
                        mod_lines.update(range(d.lineno, d.end_lineno + 1))
                visit(st.body, False)
            elif isinstance(st, ast.ClassDef):
                if at_import:
                    for d in st.decorator_list + st.bases + [k.value for k in st.keywords]:
                        mod_lines.update(range(d.lineno, d.end_lineno + 1))
                visit(st.body, at_import)
            elif at_import:
                doc = i == 0 and isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str)
                if doc or isinstance(st, (ast.Import, ast.ImportFrom, ast.Pass)):
                    continue
                if isinstance(st, (ast.Assign, ast.AnnAssign)) and isinstance(getattr(st, "value", None), ast.Constant):
                    continue
                mod_lines.update(range(st.lineno, st.end_lineno + 1))
            else:
                for sub in ast.iter_child_nodes(st):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        visit([sub], False)

    visit(tree.body, True)
    keep = sorted(i for i in imports if i and any(i == p or i.startswith(p + ".") for p in packages))
    return FileFacts(imports=keep, dynamic=sorted(dyn), dyn_lines=sorted(dyn_lines), defs=sorted(defs), mod_lines=sorted(mod_lines))


def snapshot(repo: str | Path, src_root: str, packages: list[str], dirs: list[str]) -> dict[str, FileFacts]:
    """Facts of every .py file under the given directories (paths relative to the repository)."""
    repo = Path(repo)
    root = repo / src_root if src_root not in ("", ".") else repo
    files: dict[str, FileFacts] = {}
    for d in dirs:
        for p in sorted((repo / d).rglob("*.py")) if (repo / d).exists() else []:
            rel = p.relative_to(repo).as_posix()
            files.setdefault(rel, analyse_file(p, root, packages))
    return files


def module_of(path: str, src_root: str) -> str:
    p = path[len(src_root) + 1:] if src_root not in (".", "") and path.startswith(src_root + "/") else path
    p = p[:-3]
    p = p.removesuffix("/__init__")
    return p.replace("/", ".")
