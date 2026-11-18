# 0002. Review output: rule ids, evidence-first findings, SARIF 2.1.0

Status: Accepted (November 2026)

## Context

`codetwin review` comments on pull requests like a reviewer. Its comments must be checkable (a developer
should see why a comment was made), stable across pushes (no duplicate comments), and readable by other tools.
Language-model reviewers are useful but can be wrong and can invent line numbers; the project rule is that a
language model explains and never decides (AGENTS.md).

## Decision

- Every finding names a stable rule id (`CT001`...) from one catalogue, `review/rules.py`.
- Every finding records its source: `evidence` (coverage, static analysis, calibrated risk), `linter` or
  `llm`. LLM findings are capped at medium severity, dropped when their line is not in the diff, and never make
  a review blocking.
- A fingerprint (rule, path, line, title) identifies a finding across runs; the summary comment is found by a
  hidden marker and edited in place.
- Output formats: Markdown (pull-request comment), the GitHub pull-request review API, JSON, and SARIF 2.1.0,
  the OASIS standard that GitHub code scanning and most static-analysis tools read.
- Analyzers are plugins (`review/analyzers/<name>.py`), discovered like report sections and commands, so
  people can add one without touching shared files.

## Consequences

- Teams can filter, suppress or track findings by rule in GitHub code scanning.
- Changing a rule's meaning needs a new id; the old id is retired, not reused.
- The review depends on the decision's report sections (`docs/output.md`). A failed section yields no
  findings, and `Review.notes` names it, so the summary comment says which findings may be missing.
