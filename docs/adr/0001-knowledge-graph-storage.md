# 0001. Knowledge graph: NetworkX built from the SQLite evidence store

Status: Accepted (November 2026)

## Context

The review pipeline and the planned editor features need to ask graph questions: which tests ran this
function, which files import this one, what does a change reach. Code-review tools that give a language model
repository context do this with a code knowledge graph built from syntax trees (Tree-sitter), stored either in
SQLite with NetworkX for traversal or in a graph database. Comparisons published in 2026 found that graphs derived
deterministically from syntax trees answer multi-hop code questions more reliably than graphs extracted by a
language model or plain vector search.

CodeTwin already has the facts: a normalized SQLite evidence store (migrations 0003 and 0004) with files,
symbols, static and runtime evidence edges and unresolved references, filled by Tree-sitter and coverage
adapters. Options:

1. A graph database server (Neo4j, ArcadeDB, FalkorDB): Cypher queries, but a second store to keep in sync,
   a service to run on every developer machine and CI runner, and a licence to check.
2. An embedded graph database (Kùzu): no server, but the project was archived in October 2025 and is
   maintained only by community forks.
3. NetworkX built from the SQLite store on demand.

## Decision

Option 3. The SQLite store stays the single source of truth; `codetwin.kg.build` derives a typed
`MultiDiGraph` from it. Every node and edge kind in `kg/schema.py` is filled by the builder, and every edge
records the kind of evidence that found it. Export to GraphML and node-link JSON covers visualisation and a
later move to a graph database.

## Consequences

- No new service, dependency or file format; the graph is reproducible from the store.
- Graphs must fit in memory. That holds for the repositories CodeTwin targets (thousands of files); a monorepo
  of millions of files would need option 1 or 2, fed from the same export.
- Queries are Python functions (`blast_radius`, `context`), not Cypher. New questions need code and tests.
- Cross-repository edges (from `store/analyses.py`) are not in the graph yet; adding them is a new edge kind
  plus the builder code that fills it.
