"""Code knowledge graph: one typed graph of repositories, files, symbols and tests, built from recorded evidence.

Status: built and tested; used by `codetwin kg` and by the review pipeline (context for the optional LLM
reviewer, blast radius of a change). Design decision: docs/adr/0001-knowledge-graph-storage.md.

The graph is derived, never edited: the evidence store (SQLite, docs/database.md) is the source of truth, and
the graph is rebuilt from it with NetworkX. Every edge carries the kind of evidence it came from, so a query
can answer "why is this test linked to this function?" with facts, not guesses.
"""
from __future__ import annotations

from .build import build, from_engine
from .graph import KnowledgeGraph
from .schema import EdgeKind, NodeKind

__all__ = ["EdgeKind", "KnowledgeGraph", "NodeKind", "build", "from_engine"]
