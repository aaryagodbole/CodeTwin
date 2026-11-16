# Architecture decision records

Short records of decisions that are expensive to reverse, in the format of Michael Nygard's
"Documenting Architecture Decisions": context, decision, consequences. A record is never edited after it is
accepted; a later record supersedes it.

| No. | Decision | Status |
|---|---|---|
| [0001](0001-knowledge-graph-storage.md) | Knowledge graph: NetworkX built from the SQLite evidence store, no graph database | Accepted |
| [0002](0002-review-findings-and-sarif.md) | Review output: rule ids, evidence-first findings, SARIF 2.1.0 | Accepted |

New record: copy the newest file, take the next number, set the status to *Proposed*, and open a pull request.
