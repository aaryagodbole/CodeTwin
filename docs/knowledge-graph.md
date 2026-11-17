# Code knowledge graph (`codetwin kg`)

One typed graph of the recorded commit: the repository, its source files, test files and symbols (functions,
methods, classes), linked by edges that each say which kind of evidence found them. It is built from the evidence
store (`docs/database.md`), never edited by hand, and rebuilt whenever it is needed.

```bash
codetwin kg stats                                   # node and edge counts by kind
codetwin kg blast src/shop/calc.py:5                # what a change at that line can affect
codetwin kg blast src/shop/calc.py                  # ... anywhere in the file
codetwin kg export --format graphml -o graph.graphml   # Gephi, yEd, Cytoscape, Neo4j (apoc.import.graphml)
codetwin kg export --format json -o graph.json      # node-link JSON (D3, NetworkX, the dashboard)
```

The web dashboard API also exposes the knowledge graph via `GET /api/kg` (see `dashboard/README.md`).

## Schema

| Node kind | Id | Attributes |
|---|---|---|
| `repository` | `repository:<name>` | |
| `file` | `file:<path>` | |
| `test` | `test:<path>` | |
| `symbol` | `symbol:<path>::<Qualified.name>` | `symbol_kind` (function, method, class), `file`, `start`, `end` |
| `unknown` | `unknown:<path>` | `detail` (e.g. `dynamic calls (getattr)`) |

| Edge kind | From → to | Evidence | Attributes |
|---|---|---|---|
| `contains` | repository → file/test | structure | |
| `defines` | file → symbol | static | |
| `imports` | file → file | static | |
| `covers` | test → file, test → symbol | runtime | `lines`: lines executed on the recorded commit |
| `co_changes` | file ↔ file | co-change | `commits`: times committed together (≥ 2; commits of > 30 files ignored) |
| `unresolved` | file → unknown | unresolved | `lines` of the dynamic calls |

Unresolved links are nodes, not missing edges: a query that crosses one reports it under `unknowns`
(AGENTS.md: unknown is not "no dependency").

## Blast radius

`blast_radius(changed)` takes line numbers **of the recorded commit** and returns:

- `symbols`: the innermost changed symbols;
- `files`: source files that import a changed file, up to 4 hops, each with its import chain;
- `tests`: tests that executed a changed file or symbol, with the evidence kind;
- `unknowns`: unresolved links on the way, and changed files the graph does not know.

`context(changed)` turns the same result into a short factual text. The optional LLM reviewer
(`codetwin review --llm`) puts it into the prompt, so the model sees real callers and tests instead of
code that only looks similar (graph-based retrieval).

## Why NetworkX on SQLite and not a graph database

See [ADR 0001](adr/0001-knowledge-graph-storage.md). In short: the evidence already lives in a normalized
SQLite schema, the graphs of the repositories we target fit in memory, and the embedded graph database we
considered (Kùzu) was archived in October 2025. GraphML export keeps a path open to Neo4j or another
server if a deployment ever needs one.

Status: built and tested; the paper's evaluation uses the file-level impact graph (`graph/impact.py`), not this graph.
