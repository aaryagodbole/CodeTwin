"""Data model of a review: findings and the review they belong to.

A finding is one thing a reviewer should look at. Every finding says where it is, how serious it is, which
analyzer raised it and what evidence it rests on, so a developer can check it instead of trusting it.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Ordered from most to least serious. Maps to SARIF levels and GitHub annotation levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def rank(self) -> int:
        return _RANK[self]

    @property
    def sarif_level(self) -> str:
        return {"critical": "error", "high": "error", "medium": "warning", "low": "note", "info": "note"}[self.value]


_RANK = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}


class Source(StrEnum):
    """Where a finding comes from. Evidence findings are reproducible; LLM findings are advisory."""
    EVIDENCE = "evidence"      # coverage, static analysis, calibrated risk (deterministic)
    LINTER = "linter"          # an external static analysis tool
    LLM = "llm"                # a language model's opinion; never blocks a pull request


@dataclass
class Finding:
    rule: str                              # stable id, e.g. "CT001" (see review/rules.py)
    severity: Severity
    title: str                             # one line
    message: str                           # what is wrong and why it matters (Markdown allowed)
    source: Source = Source.EVIDENCE
    path: str | None = None                # None = about the whole pull request
    start_line: int | None = None
    end_line: int | None = None
    evidence: list[str] = field(default_factory=list)   # facts the finding rests on, in plain words
    suggestion: str | None = None          # what to do about it
    analyzer: str = ""                     # module NAME that raised it (filled by the pipeline)

    @property
    def fingerprint(self) -> str:
        """Stable across runs for the same rule at the same place, so comments can be updated, not repeated."""
        key = f"{self.rule}|{self.path or ''}|{self.start_line or ''}|{self.title}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["source"] = self.source.value
        d["fingerprint"] = self.fingerprint
        return d


@dataclass
class FileSummary:
    path: str
    changed_lines: int
    tests: list[str] = field(default_factory=list)       # selected tests that cover this file
    findings: int = 0


@dataclass
class Review:
    decision: str                          # "proceed" | "abstain" (from the selection)
    residual_risk: float
    alpha: float | None
    selected: list[str]
    findings: list[Finding]
    files: list[FileSummary] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)       # analyzers that failed or were skipped, and why

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in Severity}
        for f in self.findings:
            out[f.severity.value] += 1
        return out

    @property
    def blocking(self) -> bool:
        """A pull request should not merge as is: abstention, or a critical/high evidence finding."""
        return self.decision == "abstain" or any(
            f.source is not Source.LLM and f.severity.rank <= Severity.HIGH.rank for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": 1, "decision": self.decision, "residual_risk": self.residual_risk, "alpha": self.alpha,
                "blocking": self.blocking, "counts": self.counts(), "selected": self.selected,
                "files": [asdict(f) for f in self.files], "findings": [f.to_dict() for f in self.findings],
                "notes": self.notes}
