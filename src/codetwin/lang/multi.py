"""Repositories with several languages (a Python service, a TypeScript front end, a Go tool, ...).

`Multi` combines one adapter per language: each file belongs to the adapter of its extension, each test
file runs with its own language's runner, and the evidence of all of them goes into one run and one graph.
Dependencies between languages (a TypeScript client calling a Python API over HTTP) are not visible to any
parser; coverage and co-change history still link them when the same tests exercise both.
"""
from __future__ import annotations

from pathlib import Path

from ..evidence.model import FileFacts, TestRun
from .base import Language


class Multi(Language):
    def __init__(self, cfg, adapters: list[Language]):
        super().__init__(cfg)
        self.adapters = adapters
        self.name = "+".join(a.name for a in adapters)
        self.extensions = tuple(e for a in adapters for e in a.extensions)

    def of(self, path: str) -> Language | None:
        p = path.split("::", 1)[0]
        return next((a for a in self.adapters if p.endswith(a.extensions)), None)

    def describe(self) -> str:
        return ", ".join(a.describe() for a in self.adapters)

    # --------------------------------------------------------------- files
    def is_test(self, path: str) -> bool:
        a = self.of(path)
        return bool(a and a.is_test(path))

    def is_source(self, path: str) -> bool:
        a = self.of(path)
        return bool(a and a.is_source(path))

    def list_tests(self) -> list[str]:
        return sorted({t for a in self.adapters for t in a.list_tests()})

    def stem(self, path: str) -> str:
        a = self.of(path)
        return a.stem(path) if a else super().stem(path)

    # --------------------------------------------------------------- evidence
    def facts(self) -> dict[str, FileFacts]:
        out: dict[str, FileFacts] = {}
        for a in self.adapters:
            for f, v in a.facts().items():
                if self.of(f) is a:
                    out[f] = v
        return out

    def run_suite(self, sha: str, tests: list[str] | None = None, timeout: int = 3600) -> TestRun:
        run = TestRun(sha=sha)
        codes = []
        for a in self.adapters:
            mine = [t for t in (tests if tests is not None else a.list_tests()) if self.of(t) is a]
            if not mine:
                continue
            r = a.run_suite(sha, mine, timeout)
            run.durations.update(r.durations)
            run.failing += r.failing
            run.covered.update(r.covered)
            for f, ls in r.import_lines.items():
                run.import_lines[f] = sorted(set(run.import_lines.get(f, [])) | set(ls))
            run.wall += r.wall
            codes.append(r.returncode)
        run.returncode = next((c for c in codes if c not in (0, "0")), 0)
        return run

    def _split(self, tests: list[str]) -> dict[int, list[str]]:
        groups: dict[int, list[str]] = {}
        for t in tests:
            a = self.of(t)
            if a is not None:
                groups.setdefault(self.adapters.index(a), []).append(t)
        return groups

    def run_tests(self, work: Path, tests: list[str], timeout: int) -> dict[str, bool | None]:
        out: dict[str, bool | None] = {t: None for t in tests}
        for i, ts in self._split(tests).items():
            out.update(self.adapters[i].run_tests(work, ts, timeout))
        return out

    def has_runtime_evidence(self, path: str) -> bool:
        a = self.of(path)
        return a is not None and a.has_runtime_evidence(path)

    def run_all(self, work: Path, tests: list[str], timeout: int) -> bool:
        return all([self.adapters[i].run_all(work, ts, timeout) for i, ts in self._split(tests).items()])

    def build_ok(self, work: Path, timeout: int) -> bool:
        return all(a.build_ok(work, timeout) for a in self.adapters)

    def classify_source(self, old: str, new: str, path: str) -> str:
        a = self.of(path)
        return a.classify_source(old, new, path) if a else "semantic"

    def extreme_mutant(self, text: str, fn: list[int], path: str) -> str | None:
        a = self.of(path)
        return a.extreme_mutant(text, fn, path) if a else None

    def make_copy(self, dst: Path) -> None:
        Language.make_copy(self, dst)
