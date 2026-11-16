"""Review analyzers (auto-discovered). One file per analyzer.

An analyzer module defines::

    NAME = "untested_change"
    DEFAULT = True                                        # runs unless switched off in [review] analyzers
    def analyze(ctx: ReviewContext) -> list[Finding]: ...

Analyzers read the context only. They must not change the selection, the decision or the evidence store
(AGENTS.md: the LLM explains, never decides; the same holds for every reviewer).
"""
