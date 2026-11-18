"""Pull-request review: evidence-based findings, posted like a human reviewer's comments.

Status: built and tested (`codetwin review`), not yet evaluated in the paper. Design: docs/review.md and
docs/adr/0002-review-findings-and-sarif.md.

Layers::

    Engine.select()  ->  ReviewContext  ->  analyzers/<name>.py (auto-discovered)  ->  Review
                                                                                       |
                                     render.markdown / render.github / render.sarif / to_dict

Evidence analyzers turn what CodeTwin already knows (calibrated risk, coverage, unresolved calls, contracts,
connected repositories) into findings at a file and line. The optional LLM analyzer adds advisory comments,
with context taken from the knowledge graph (`codetwin.kg`); it can never make a review blocking.
"""
from __future__ import annotations

from .context import ReviewContext
from .model import Finding, Review, Severity, Source
from .pipeline import run, select_analyzers

__all__ = ["Finding", "Review", "ReviewContext", "Severity", "Source", "run", "select_analyzers"]
