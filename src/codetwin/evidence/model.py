"""Data types shared by the evidence layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EvidenceType(str, Enum):  # noqa: UP042  (Python 3.10 inside benchmark images)
    """How a link between code and tests was found (Section IV-C of the paper)."""
    STATIC = "static"            # found in the syntax tree (imports)
    RUNTIME = "runtime"          # observed by per-test coverage
    DECLARED = "declared"        # manifest or API contract (planned)
    CO_CHANGE = "co-change"      # files that change together in history
    SUGGESTED = "suggested"      # proposed by a language model, not verified (planned)
    UNRESOLVED = "unresolved"    # a link exists but cannot be resolved (e.g. getattr with a computed name)


@dataclass
class FileDiff:
    status: str                  # M, A, D or R
    old_path: str
    old: list[int] = field(default_factory=list)   # changed/removed lines in the old version (insertion points included)
    new: list[int] = field(default_factory=list)   # changed/added lines in the new version


@dataclass
class FileFacts:
    imports: list[str] = field(default_factory=list)
    dynamic: list[str] = field(default_factory=list)       # kinds of dynamic calls in the file
    dyn_lines: list[int] = field(default_factory=list)
    defs: list[list[int]] = field(default_factory=list)    # [start (incl. decorators), end, first body line]
    mod_lines: list[int] = field(default_factory=list)     # statements that run at import time
    deps: list[str] = field(default_factory=list)          # project files this file depends on (resolved imports)
    symbols: list[list] = field(default_factory=list)      # [qualified name, kind, first line, last line]


@dataclass
class TestRun:
    """Result of running the suite once with per-test coverage."""
    sha: str
    durations: dict[str, float] = field(default_factory=dict)            # test file -> seconds
    failing: list[str] = field(default_factory=list)                     # failing test case ids
    covered: dict[str, dict[str, list[int]]] = field(default_factory=dict)  # test file -> source file -> lines
    import_lines: dict[str, list[int]] = field(default_factory=dict)     # source file -> lines run at import time
    returncode: int | str = 0
    wall: float = 0.0
    notes: list[str] = field(default_factory=list)                         # problems of the run itself (not stored)
    unrun: list[str] = field(default_factory=list)       # listed but not executed (no runner, tool missing): no outcome
