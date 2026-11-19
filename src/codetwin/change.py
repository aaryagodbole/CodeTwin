"""The Change module: everything known about one change before its tests run.

A `ChangeContext` is built once by `Engine.change()` and read by selection, learning, report sections, commands,
MCP tools and the server. It answers, for one recorded base commit:

- the baseline: the base commit, its recorded run and its static facts;
- the change: the changed lines of the working tree against the base;
- the working tree: its static facts and its tests, parsed once and shared;
- co-change history, read only up to the base (no look-ahead, E5);
- the feature rows of every test, and the impact graph of the changed files;
- what weakens the evidence (thin history, an incomplete or skipped run, files without runtime evidence).

Everything is computed on first use and cached, so a caller pays only for what it reads. Only evidence that
exists before the change's tests run is reachable from here: the new run belongs to `Engine.learn()`.
"""
from __future__ import annotations

from functools import cached_property
from typing import Any, Protocol

from .evidence.model import FileDiff, FileFacts, TestRun
from .graph.impact import Impact, build_graph, impact_of
from .risk import features


class Workspace(Protocol):
    """What a change reads from its project (an `Engine`): configuration, language, store, and the git and parser
    queries. Typed here instead of importing the engine, which imports this module."""
    cfg: Any
    lang: Any
    store: Any
    root: Any

    def changed(self, base: str, head: str | None = None) -> dict[str, FileDiff]: ...
    def facts_now(self) -> dict[str, FileFacts]: ...
    def tests_now(self) -> list[str]: ...
    def history(self, base: str | None = None) -> list[list[str]]: ...
    def history_note(self, base: str | None = None) -> str | None: ...


class ChangeContext:
    """One change against one recorded base commit. Build it with `Engine.change()`."""

    def __init__(self, engine: Workspace, base: str, prev: TestRun | None, diff: dict[str, FileDiff] | None = None,
                 chosen: bool = False):
        self._eng = engine
        self.base = base                  # recorded commit the change is compared with
        self.prev = prev                  # its recorded run (None only when built with require_run=False)
        self.chosen = chosen              # the caller named the base, so no newer run was skipped for them
        if diff is not None:
            self.__dict__["diff"] = diff  # already known: fills the cached property below

    @cached_property
    def diff(self) -> dict[str, FileDiff]:
        """file -> FileDiff: changed lines of the working tree against `base` (read from git on first use)."""
        return self._eng.changed(self.base)

    # ------------------------------------------------------------------ configuration
    @property
    def cfg(self) -> Any:
        return self._eng.cfg

    @property
    def lang(self) -> Any:
        return self._eng.lang

    @property
    def store(self) -> Any:
        return self._eng.store

    @property
    def root(self) -> Any:
        return self._eng.root

    def is_source(self, path: str) -> bool:
        return self.lang.is_source(path)

    # ------------------------------------------------------------------ the change
    @cached_property
    def source_files(self) -> list[str]:
        """Changed source files (not tests), sorted."""
        return sorted(f for f in self.diff if self.is_source(f))

    @property
    def source_changed(self) -> bool:
        return bool(self.source_files)

    def changed_since(self, rev: str) -> dict[str, FileDiff]:
        """Changed lines of the working tree against another commit (e.g. a pull request's base for review)."""
        return self.diff if rev == self.base else self._eng.changed(rev)

    # ------------------------------------------------------------------ evidence (cached)
    @cached_property
    def static_base(self) -> dict[str, FileFacts]:
        """Static facts recorded at the base commit."""
        return self.store.get_static(self.base)

    @cached_property
    def facts_now(self) -> dict[str, FileFacts]:
        """Static facts of the working tree, parsed once for every reader of this change."""
        return self._eng.facts_now()

    @cached_property
    def tests_now(self) -> list[str]:
        return self._eng.tests_now()

    @cached_property
    def tests(self) -> list[str]:
        """Every test the decision can choose: recorded at the base or present now."""
        recorded = set(self.prev.durations) if self.prev else set()
        return sorted(recorded | set(self.tests_now))

    @cached_property
    def history(self) -> list[list[str]]:
        """Files of earlier commits for co-change, read up to the base only (E5)."""
        return self._eng.history(self.base)

    @cached_property
    def rows(self) -> dict[str, dict]:
        """Feature rows of every test (the risk model's input)."""
        if self.prev is None:
            raise RuntimeError(f"no recorded run for {self.base[:10]}; run `codetwin record` there first")
        return features.compute(self.diff, self.prev, self.static_base, self.facts_now, self.tests,
                                self.cfg.src_root, self.is_source, self.history, self.lang.stem)

    def impact(self, files: list[str] | None = None) -> Impact:
        """Tests that reach `files` (default: the changed source files), with unresolved links as unknowns."""
        g = build_graph(self.facts_now, self.prev)
        return impact_of(g, self.source_files if files is None else files, self.tests_now)

    @cached_property
    def without_runtime_evidence(self) -> dict[str, str]:
        """Changed source files whose tests have no runtime evidence, with the reason: no runner configured, or a
        runner whose runs recorded no coverage at all for the file's project (e.g. a missing coverage tool)."""
        # groups of the source files any test executed (a test project may live apart from the code it tests)
        covered = {self.lang.evidence_group(f) for files in (self.prev.covered.values() if self.prev else [])
                   for f in files}
        out: dict[str, str] = {}
        for f in self.source_files:
            if not self.lang.has_runtime_evidence(f):
                out[f] = "no test runner configured"
            elif self.lang.evidence_group(f) not in covered:
                out[f] = "no coverage recorded for this project's tests"
        return out

    @cached_property
    def evidence_notes(self) -> list[str]:
        """What weakens this change's evidence: thin git history, an incomplete run at the base, or a newer run
        that was skipped because it did not complete."""
        note = self._eng.history_note(self.base)
        notes = [note] if note else []
        if self.prev is not None and self.prev.incomplete:
            notes.append(f"the recorded run of {self.base[:10]} did not complete ({self.prev.returncode}): its "
                         "coverage is partial")
        skipped = None if self.chosen else self.store.latest_run_incomplete()
        if skipped and skipped[0] != self.base:
            notes.append(f"the newest recorded run ({skipped[0][:10]}) did not complete ({skipped[1]}); comparing with "
                         f"the older complete run of {self.base[:10]} instead")
        return notes
