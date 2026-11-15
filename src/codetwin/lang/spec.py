"""Declarative description of one language for the generic tree-sitter adapter.

A new language is one file in `lang/specs/` that defines `SPEC = Spec(...)`; it is discovered automatically.
Only `name`, `grammars` and `test_globs` are required. Without a runner preset the user sets `test_command`
and `coverage_format` in `.codetwin.toml`; without `imports`/`resolve` the static graph is empty and CodeTwin
relies on coverage (and reports that it has no static evidence).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Node = Any   # tree_sitter.Node


@dataclass
class Runner:
    """How to run one test id with coverage. Placeholders in the commands:
    {test} test file path, {cov_dir} empty folder for the coverage report, plus anything `vars(test_id, text)`
    returns (e.g. {names} for Go test functions, {test_class} for JUnit)."""
    name: str
    test_command: str
    coverage_format: str                         # lcov | gocover | jacoco | cobertura | clover
    coverage_file: str | None = None             # glob under {cov_dir}; "./<glob>" is under the project folder
                                                 # (tools that ignore an output option); default per format
    run_command: str | None = None               # without coverage (weakcheck); default: test_command
    setup_command: str | None = None             # once per recorded run (e.g. compile)
    build_command: str | None = None             # does a mutated copy still compile? (weakcheck)
    result_glob: str | None = None               # JUnit XML written by the run (pass/fail per test case)
    detect: Callable[[Path], bool] = lambda root: True
    vars: Callable[..., dict[str, str | list[str]]] | None = None   # (test id, file text[, project folder]) -> values
    env: dict[str, str] | None = None            # extra environment variables (placeholders allowed)
    shares_build_dir: bool = False               # writes build output inside the project (target/, build/, obj/):
                                                 # test files of one project never run in parallel

    def parallel_safe(self) -> bool:
        """Can two test files of the same project run at once? Not if the runner shares build output or writes
        its coverage or JUnit reports inside the project folder."""
        return not (self.shares_build_dir or self.result_glob or (self.coverage_file or "").startswith("./"))


@dataclass
class Spec:
    name: str
    grammars: dict[str, str]                     # file extension -> tree-sitter grammar name
    test_globs: list[str]
    exclude_globs: list[str] = field(default_factory=list)   # never tests even when a test glob matches
    helper_globs: list[str] = field(default_factory=list)    # not tests unless the name itself says test/spec
    markers: list[str] = field(default_factory=list)          # files whose presence suggests this language
    source_dirs: list[str] = field(default_factory=list)      # candidates for `codetwin init`
    tests_dirs: list[str] = field(default_factory=list)
    function_types: set[str] = field(default_factory=set)
    decl_types: set[str] = field(default_factory=set)         # top-level nodes that are not load-time code
    comment_types: set[str] = field(default_factory=lambda: {"comment", "line_comment", "block_comment"})
    annotation_types: set[str] = field(default_factory=set)   # type-only syntax, removed for 'annotation'
    container_types: set[str] = field(default_factory=set)    # top-level wrappers looked into (export, #ifdef)
    load_time: Callable[[Node, bytes], set[int]] | None = None  # replaces the top-level rule for load-time lines
    imports: Callable[[Node, bytes], list[str] | None] | None = None
    dynamic: Callable[[Node, bytes], str | None] | None = None
    names: Callable[[Node, bytes], str | None] | None = None  # referenced identifiers kept for `extra_deps`
    prepare: Callable[[Any], None] | None = None              # precompute index data (module path, packages)
    resolve: Callable[[str, str, Any], list[str]] | None = None
    extra_deps: Callable[[str, Any], list[str]] | None = None
    mutant: Callable[[Node, bytes, str], tuple[int, int, str] | None] | None = None
    runners: list[Runner] = field(default_factory=list)
    test_ids: Callable[[Path, str], list[str]] | None = None  # extra test ids in a source file (Rust unit tests)
    auto: bool = False                                        # built by lang/auto.py: generic node-type rules
