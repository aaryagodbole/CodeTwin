# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Every pull request adds a line under **Unreleased**
(Added / Changed / Fixed / Removed), so a regression can be traced to the change that introduced it.

## [Unreleased]

## [0.1.0] - 2026-11-10

Baseline release: the structure every later pull request is compared against.

### Added
- Engine with four layers: evidence (git diff, AST facts, per-test coverage), SQLite evidence store and typed
  impact graph, risk model with conformal calibration and adaptive level, residual-risk estimate with abstention.
- CLI: `init`, `record`, `select` (calibrated and budget modes, `--json`), `learn`, `impact`, `explain`.
- MCP server with `verify_change`, `get_impact`, `recommend_tests`, `explain_decision`.
- Extension points: one file per CLI command (`commands/`), MCP tool (`mcp_tools/`), report section (`report/`),
  database migration (`store/migrations/`) and VS Code feature (`extensions/vscode/src/features/`).
- Output contract `schema: 1` for `select --json` (docs/output.md).
- `codetwin graph`: impact graph around a file or selected lines, with evidence-typed edges; MCP `get_graph`.
- VS Code extension (preview): impact graph of a selection beside the editor (Cytoscape), hover summary,
  follow-selection; select tests, impact of file, record, explain, status bar; prompt to install the CLI.
- Web dashboard (Next.js, static export): overview, system map, decisions, results (observed miss rate vs
  target), impact graph of a file; `codetwin serve` serves it with a read-only FastAPI API.
- GitHub composite action (record on base, select, job summary, run selected tests).
- CI (lint, tests with coverage gate, package build, CLI smoke test, extension and dashboard builds) and release
  workflow (GitHub Release always; VS Code Marketplace, Open VSX and PyPI once configured).

[Unreleased]: https://github.com/aaryagodbole/CodeTwin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aaryagodbole/CodeTwin/releases/tag/v0.1.0
