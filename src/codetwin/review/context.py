"""What every analyzer receives. Built once per review from the decision and the diff."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReviewContext:
    root: Path
    decision: dict                          # Decision.to_dict(): the output contract of `select --json`
    changed: dict[str, list[int]]           # file -> changed lines in the new version
    cfg: Any = None                         # codetwin.config.Config, or None outside a project
    graph: Any = None                       # codetwin.kg.KnowledgeGraph, if one was built
    llm: Any = None                         # codetwin.llm.LLMClient, only when the user switched it on
    options: dict = field(default_factory=dict)

    def section(self, name: str) -> dict:
        """One report section of the decision (`extras.<name>`), or {} if absent or failed."""
        sec = (self.decision.get("extras") or {}).get(name)
        return sec if isinstance(sec, dict) and "error" not in sec else {}

    def in_diff(self, path: str | None, line: int | None) -> bool:
        """GitHub can only attach an inline comment to a line that is part of the diff."""
        return bool(path and line and line in set(self.changed.get(path, [])))
