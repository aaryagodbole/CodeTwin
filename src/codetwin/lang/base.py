"""The contract between the language-neutral core and one programming language.

Everything above this layer (features, risk model, calibration, abstention, reports, interfaces) reads only
`TestRun` (which test file executed which lines, how long it took, whether it failed) and `FileFacts`
(dependencies, dynamic constructs, function spans, load-time statements). A language adapter produces those
two from a repository, and can additionally classify no-op edits and build extreme mutants for `weakcheck`.

Adapters: `python.py` (ast + pytest + coverage.py) and `generic.py` (tree-sitter + any test runner that can
write LCOV, Go, JaCoCo, Cobertura or Clover coverage), configured per language by a spec in `specs/`.
"""
from __future__ import annotations

import re
import shutil
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from ..evidence.model import FileFacts, TestRun

if TYPE_CHECKING:
    from ..config import Config

SKIP_DIRS = {".git", ".codetwin", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build",
             "target", "vendor", ".gradle", ".idea", ".mypy_cache", ".pytest_cache", "coverage", ".next", "out",
             "bin", "obj"}


def under(path: str, dirs: list[str]) -> bool:
    """`path` lies in one of `dirs` ("." or "" means the whole repository)."""
    return not dirs or any(d in ("", ".") or path == d or path.startswith(d.rstrip("/") + "/") for d in dirs)


@lru_cache(maxsize=512)
def _glob_re(pattern: str) -> re.Pattern:
    """Glob with `**` (any number of folders, possibly none) and `*`/`?` that never cross a `/`."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def glob_match(path: str, patterns: list[str]) -> bool:
    """Patterns without a `/` match the file name; others match the whole repository-relative path."""
    name = path.rsplit("/", 1)[-1]
    return any(_glob_re(p).match(path if "/" in p else name) for p in patterns)


# folders of sample or fixture code: real code of their own language, but not what the repository is about
SAMPLE_DIRS = {"examples", "example", "samples", "sample", "fixtures", "fixture", "testdata", "test_data",
               "third_party", "third-party", "docs", "doc"}


def repo_files(root: Path, extensions: tuple[str, ...], dirs: list[str] | None = None,
               skip: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Repository-relative paths of files with one of `extensions`, skipping build and dependency folders
    (and, directly under the repository root, the folder names in `skip`: a Java package `com/example` deeper
    down is code, a top-level `examples/` is not)."""
    out: list[str] = []
    bases = [root / d for d in (dirs or ["."]) if (root / d).exists()]
    seen: set[Path] = set()
    for b in bases:
        if b.is_file():
            if b.suffix in extensions and b not in seen:
                seen.add(b)
                out.append(b.relative_to(root).as_posix())
            continue
        stack = [b]
        while stack:
            d = stack.pop()
            for p in sorted(d.iterdir()):
                if p.is_dir():
                    top = p.parent == root
                    if p.name not in SKIP_DIRS and not (top and p.name in skip) and not p.name.startswith("."):
                        stack.append(p)
                elif p.name.endswith(extensions) and p not in seen:
                    seen.add(p)
                    out.append(p.relative_to(root).as_posix())
    return sorted(out)


class Language:
    """Base adapter. Subclasses fill in the language-specific parts."""

    name = "base"
    extensions: tuple[str, ...] = ()
    uses_packages = False          # reads `packages` from the configuration (coverage measured per package)
    mutates_every_function = False  # extreme_mutant supports every function (None then means it failed)
    # How a change that leaves the code's meaning untouched is described (report section semantic_noop).
    noop_description = ("semantic no-op (syntax tree unchanged apart from comments and formatting): only added or "
                        "changed tests are needed")

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.root = cfg.root

    # --------------------------------------------------------------- files
    def is_test(self, path: str) -> bool:
        raise NotImplementedError

    def is_source(self, path: str) -> bool:
        return path.endswith(self.extensions) and not self.is_test(path) and under(path, self.cfg.source_dirs)

    def list_tests(self) -> list[str]:
        """Test ids (normally test file paths) present in the working tree."""
        raise NotImplementedError

    def stem(self, path: str) -> str:
        """Module-like name used by the name-match feature (`src/foo.ts` -> `foo`, `src/foo/index.ts` -> `foo`).
        Entry-point names that say nothing about the code (`main`, `lib`) give "" (no name match)."""
        parts = path.split("/")
        name = parts[-1].split(".", 1)[0]
        if name in ("index", "mod", "__init__") and len(parts) > 1:
            name = parts[-2]
        return "" if name in ("main", "lib", "index", "mod") else name

    # --------------------------------------------------------------- evidence
    def facts(self) -> dict[str, FileFacts]:
        """Static facts of every source and test file of the working tree, with `deps` resolved to files."""
        raise NotImplementedError

    def run_suite(self, sha: str, tests: list[str] | None = None, timeout: int = 3600) -> TestRun:
        """Run `tests` (default: all) with per-test coverage."""
        raise NotImplementedError

    def run_tests(self, work: Path, tests: list[str], timeout: int) -> dict[str, bool | None]:
        """Run tests in a copy of the repository without coverage: test id -> passed (None: could not run)."""
        raise NotImplementedError

    copy_ignore: tuple[str, ...] = (".git", ".codetwin", "node_modules", "__pycache__", ".venv", "venv", ".tox",
                                    "*.pyc", "target", ".gradle", "coverage")
    link_dirs: tuple[str, ...] = ("node_modules",)

    def make_copy(self, dst: Path) -> None:
        """A scratch copy of the working tree for mutation runs. Large dependency folders (node_modules) are
        linked, not copied: mutants never touch them."""
        shutil.copytree(self.root, dst, ignore=shutil.ignore_patterns(*self.copy_ignore), symlinks=True)
        for name in self.link_dirs:
            for depth in ("", "*/", "*/*/"):
                for p in self.root.glob(f"{depth}{name}"):
                    if p.is_dir() and "node_modules" not in p.relative_to(self.root).parts[:-1]:
                        target = dst / p.relative_to(self.root)
                        if not target.exists() and target.parent.exists():
                            target.symlink_to(p.resolve(), target_is_directory=True)

    def has_runtime_evidence(self, path: str) -> bool:
        """Can tests of this file's language be run with coverage (is a test runner known)?"""
        return True

    def evidence_group(self, path: str) -> str:
        """The project a source file belongs to (its language; its project folder for adapters that run tests per
        folder). If no recorded test executed any file of the group, the group has no runtime evidence, even with
        a runner configured (e.g. its coverage tool is not installed)."""
        return self.name

    def run_all(self, work: Path, tests: list[str], timeout: int) -> bool:
        """Run `tests` and say whether all passed (output goes to the terminal where the runner prints it)."""
        return all(v is True for v in self.run_tests(work, tests, timeout).values())

    def build_ok(self, work: Path, timeout: int) -> bool:
        """Does the (possibly mutated) copy still compile? Interpreted languages: always True."""
        return True

    # --------------------------------------------------------------- change kinds and mutants
    def classify_source(self, old: str, new: str, path: str) -> str:
        """'noop', 'annotation', 'semantic' or 'unparsable' for one changed file."""
        return "semantic"

    def extreme_mutant(self, text: str, fn: list[int], path: str) -> str | None:
        """`text` with the function spanning `fn` = [start, end, body_first] made to return a default value
        without doing anything (extreme mutation). None if this language or function is not supported."""
        return None

    # --------------------------------------------------------------- init
    def guess_config(self) -> dict:
        """Values for `codetwin init`: source_dirs, tests_dir and language-specific settings."""
        return {}

    def describe(self) -> str:
        return self.name

    def config_table(self) -> str:
        """The `[lang.<name>]` table `codetwin init` writes for this language in a multi-language repository."""
        from ..config import _toml_list
        g = self.guess_config()
        runner = g.get("runner") or self.runners_by_folder() or "none found: static evidence only until you set test_command"
        return (f"[lang.{self.name}]\nsource_dirs = {_toml_list(g['source_dirs'])}\ntests_dir = \"{g['tests_dir']}\"\n"
                f"# test runner: {runner}; override with a [lang.{self.name}.runner] table (docs/languages.md)\n")

    def runners_by_folder(self) -> str | None:
        """For a monorepo whose build files sit in sub-folders: which runner each project folder uses, as text."""
        return None

    def config_file(self) -> str:
        """The `.codetwin.toml` `codetwin init` writes for a repository in this language only."""
        from ..config import GENERIC_TEMPLATE, _toml_list
        g = self.guess_config()
        return GENERIC_TEMPLATE.format(language=self.name, source_dirs=_toml_list(g["source_dirs"]),
                                       tests_dir=g["tests_dir"],
                                       runner=g.get("runner") or "none found (static evidence only until you set "
                                                                 "test_command)")
