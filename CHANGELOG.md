# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Every pull request adds a line under **Unreleased**
(Added / Changed / Fixed / Removed), so a regression can be traced to the change that introduced it.

## [Unreleased]

### Added
- README: step-by-step development setup for first-time contributors, with Windows (Git Bash) instructions.
- CI: `windows` job runs the full checks and the README commands on Windows for every pull request;
  `.gitattributes` keeps LF line endings so bash scripts work on Windows.
- Report section `semantic_noop`: detects changes that only touch docstrings, comments or formatting (AST unchanged)
  and lists the tests that suffice; annotation-only changes are reported separately and still run tests.
- Report section `change_risk`: calibrated change-level risk q(c) of the selection next to the product formula r(c)
  (prior weights from study v3; refitted from labelled changes once 40 exist). Advisory: decisions still use r(c).
- Report section `promise`: observed miss rate of the last 50 labelled calibrated decisions with a 95% Wilson
  interval, and an alert when even its lower end is above the target.
- Command `codetwin weakcheck`: extreme mutation of each changed function, run against the tests that executed it,
  to find functions that are executed but not checked.
- `codetwin learn` labels the change-level features of the decision it learns from (`change_points`).

### Changed
- Dependabot keeps the minimum versions in `pyproject.toml` and only proposes Python updates when a release
  falls outside the allowed range (CI already tests the latest versions).

## [0.1.0] - 2026-11-13

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
- CI: type checking (mypy), Python 3.13, ruff security and bug rules, `pip-audit` and `npm audit`,
  the repository's own Action on pull requests, read-only default token permissions.
- Rulesets for `main`, `dev` and release tags (`.github/rulesets/`), Codespaces dev container, `SECURITY.md`,
  `docs/github-setup.md`, `release` environment for store tokens.
- LLM settings for explanations: Groq (default) and Gemini (fallback) through their OpenAI-compatible APIs,
  `[llm]` in `.codetwin.toml`, keys from `GROQ_API_KEY` / `GEMINI_API_KEY`, automatic fallback on a missing key
  or rate limit, `codetwin llm [--test]`, `GET /api/llm` status for the dashboard (docs/llm.md).

### Changed
- TypeScript 6.0 for the dashboard and the VS Code extension (TypeScript 7 waits for typescript-eslint support;
  Dependabot ignores it until then). The extension's tsconfig lists `types: ["node"]`, which TypeScript 6 requires.
- Dependencies: GitHub Actions on Node 24 versions (checkout v7, setup-python v7, setup-node v7, upload-artifact v7,
  download-artifact v8); React 19.3.1, Tailwind CSS 4.3.5.

### Security
- GitHub Action: event and repository values (branch name, alpha, selected test file names) are passed through
  environment variables and argument lists, never into shell code; test files with shell syntax in their names
  can no longer run commands.
- VS Code extension: disabled in untrusted workspaces; `codetwin.cliPath` and `codetwin.installCommand` can only
  be set in user or machine settings, so a repository cannot choose which program runs.

### Fixed (found in review before the release)
- Release: the tag is pushed before the GitHub release is created (creating both in one API call was refused
  with HTTP 403); the source package contains only the Python project (it included `dashboard/node_modules`,
  162 MB, now 0.5 MB).
- `codetwin learn` refuses to learn twice from the same decision (it counted the change twice in calibration).
- Budget-mode outcomes no longer move the adaptive level, which tracks the calibrated threshold only.
- Database connections are closed after every CLI command, MCP call and API request.
- Coverage evidence is merged with sets instead of re-sorting per context (faster on large suites).

[Unreleased]: https://github.com/aaryagodbole/CodeTwin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aaryagodbole/CodeTwin/releases/tag/v0.1.0
