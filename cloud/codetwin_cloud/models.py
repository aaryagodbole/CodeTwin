"""The upload format `codetwin.report/v1` (docs/cloud.md, "Report format"). Validated strictly: unknown fields are
rejected, so nothing outside the documented, policy-approved fields (docs/data-policy.md) can be stored."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SHA = r"^[0-9a-f]{7,64}$"
REPO = r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Engine(Strict):
    version: str = Field(max_length=40)
    output_schema: int = Field(ge=1)


class Commit(Strict):
    head: str = Field(pattern=SHA)
    base: str | None = Field(default=None, pattern=SHA)
    ref: str | None = Field(default=None, max_length=255)
    pull_request: int | None = Field(default=None, ge=1)


class Run(Strict):
    source: Literal["github-actions", "cli"]
    id: str = Field(min_length=1, max_length=64)
    attempt: int = Field(default=1, ge=1)


class TestRow(Strict):
    id: str = Field(max_length=500)
    selected: bool
    score: float | None = None
    seconds: float | None = Field(default=None, ge=0)


class Decision(Strict):
    decision: Literal["proceed", "abstain"]
    residual_risk: float = Field(ge=0, le=1)
    alpha: float | None = Field(default=None, gt=0, lt=1)
    threshold: float | None = None
    mode: str = Field(max_length=80)
    selected: list[str] = Field(max_length=20000)
    tests: list[TestRow] = Field(default_factory=list, max_length=20000)
    reasons: list[str] = Field(default_factory=list, max_length=200)
    # Report sections that opted in with PUBLISH = True (docs/cloud.md). Free-form per section, size-limited overall.
    sections: dict[str, dict] = Field(default_factory=dict, max_length=50)


class Outcome(Strict):
    missed: bool
    failing: list[str] = Field(default_factory=list, max_length=5000)


class Report(Strict):
    report_schema: Literal["codetwin.report/v1"] = Field(alias="schema")
    engine: Engine
    repository: str = Field(pattern=REPO)
    commit: Commit
    run: Run
    decision: Decision
    outcome: Outcome | None = None

    @property
    def owner_name(self) -> tuple[str, str]:
        owner, name = self.repository.split("/", 1)
        return owner, name
