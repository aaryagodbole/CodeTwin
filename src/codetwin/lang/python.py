"""Python: syntax trees from `ast`, per-test coverage from pytest + coverage.py dynamic contexts.

This adapter wraps the original evidence code (evidence/static.py, coverage.py, noop.py, weakcheck.py)
unchanged, so results on Python projects are the same as before languages became pluggable.
"""
from __future__ import annotations

import os
import posixpath
import subprocess
import sys
from pathlib import Path

from ..evidence import coverage, static
from ..evidence.model import FileFacts, TestRun
from ..evidence.noop import classify_source
from .base import Language, repo_files, under


def import_roots(root: Path) -> list[str]:
    """Folders that hold top-level Python packages (`backend/src` for `backend/src/shop/__init__.py`), for
    repositories where Python is one part among others and no package list is configured."""
    roots: set[str] = set()
    for f in repo_files(root, (".py",)):
        if f.endswith("__init__.py"):
            pkg = posixpath.dirname(f)
            parent = posixpath.dirname(pkg)
            if not (root / parent / "__init__.py").exists() or parent == "":
                roots.add(parent or ".")
    return sorted(roots) or ["."]


def resolve_deps(files: dict[str, FileFacts], src_root: str, extra_roots: list[str] | None = None) -> None:
    """Fill `deps` from dotted imports: the longest known module prefix of each import (as before). With
    `extra_roots`, a file is also known under its module name relative to each root that contains it."""
    known = {static.module_of(f, src_root): f for f in files}
    for r in extra_roots or []:
        for f in files:
            if r in (".", "") or f.startswith(r.rstrip("/") + "/"):
                known.setdefault(static.module_of(f, r), f)
    for f, facts in files.items():
        deps: list[str] = []
        for imp in facts.imports:
            parts = imp.split(".")
            for k in range(len(parts), 0, -1):
                tgt = known.get(".".join(parts[:k]))
                if tgt:
                    if tgt != f and tgt not in deps:
                        deps.append(tgt)
                    break
        facts.deps = deps


class Python(Language):
    name = "python"
    extensions = (".py",)

    copy_ignore = (".git", ".codetwin", "node_modules", "__pycache__", ".venv", "venv", ".tox", "*.pyc")
    link_dirs = ()

    def __init__(self, cfg):
        super().__init__(cfg)
        # A configuration with packages is a Python project as before. Without packages (Python as one part of
        # a larger repository), import roots are found from the package folders and tests anywhere.
        self.discovered = not cfg.packages
        self.roots = import_roots(self.root) if self.discovered else [cfg.src_root]

    def _tests_dir_used(self) -> bool:
        td = self.cfg.tests_dir.strip("/")
        return td not in ("", ".") and (self.root / td).is_dir()

    def is_test(self, path: str) -> bool:
        name = path.rsplit("/", 1)[-1]
        if self.discovered and not self._tests_dir_used():
            return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in "/" + path
        return path.startswith(self.cfg.tests_dir.rstrip("/") + "/") or name.startswith("test_")

    def is_source(self, path: str) -> bool:
        return not self.is_test(path) and path.endswith(".py") and under(path, self.cfg.source_dirs) \
            and (bool(self.cfg.source_dirs) or self.discovered)

    def list_tests(self) -> list[str]:
        if self.discovered and not self._tests_dir_used():
            return [f for f in repo_files(self.root, (".py",))
                    if posixpath.basename(f).startswith("test_") or f.endswith("_test.py")]
        d = self.root / self.cfg.tests_dir
        return sorted(p.relative_to(self.root).as_posix() for p in d.rglob("test_*.py")) if d.exists() else []

    def stem(self, path: str) -> str:
        return path.rsplit("/", 1)[-1][:-3]

    def facts(self) -> dict[str, FileFacts]:
        if not self.discovered:
            files = static.snapshot(self.root, self.cfg.src_root, self.cfg.packages,
                                    self.cfg.source_dirs + [self.cfg.tests_dir])
            resolve_deps(files, self.cfg.src_root)
            return files
        dirs = [*self.cfg.source_dirs, self.cfg.tests_dir] if self.cfg.source_dirs else ["."]
        # repo_files skips virtual environments, node_modules and build folders
        files = {f: static.analyse_file(self.root / f, self.root, []) for f in repo_files(self.root, (".py",), dirs)}
        resolve_deps(files, ".", self.roots)
        return files

    def run_suite(self, sha: str, tests: list[str] | None = None, timeout: int = 3600) -> TestRun:
        if not self.discovered:
            return coverage.run_suite(self.root, sha, self.cfg.tests_dir, self.cfg.packages, self.cfg.src_root,
                                      tests, timeout)
        return coverage.run_suite(self.root, sha, self.cfg.tests_dir, [], os.pathsep.join(self.roots),
                                  tests if tests is not None else self.list_tests(), timeout, rootdir=True)

    def _env(self, work: Path) -> dict:
        # no bytecode cache: two mutants of one file can have equal size and mtime, and a stale .pyc would be run
        return dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                    PYTHONPATH=os.pathsep.join([*(str(work / r) for r in self.roots), os.environ.get("PYTHONPATH", "")]))

    def run_tests(self, work: Path, tests: list[str], timeout: int) -> dict[str, bool | None]:
        res: dict[str, bool | None] = {}
        for t in tests:
            try:
                r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                                    *([f"--rootdir={work}"] if self.discovered else []), t],
                                   cwd=work, env=self._env(work), capture_output=True, text=True, timeout=timeout)
                res[t] = True if r.returncode == 0 else (False if r.returncode == 1 else None)
            except subprocess.TimeoutExpired:
                res[t] = None
        return res

    def run_all(self, work: Path, tests: list[str], timeout: int) -> bool:
        """One pytest run for all files (faster than one run per file)."""
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", *([f"--rootdir={work}"] if self.discovered else []),
                                *tests], cwd=work, env=self._env(work),
                               timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return False
        return r.returncode == 0

    def classify_source(self, old: str, new: str, path: str) -> str:
        return classify_source(old, new)

    def extreme_mutant(self, text: str, fn: list[int], path: str) -> str | None:
        from ..evidence.weakcheck import _mutate
        return _mutate(text, fn[0], fn[2], fn[1])

    def guess_config(self) -> dict:
        from ..config import guess
        return guess(self.root)
