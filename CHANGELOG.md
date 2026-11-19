# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Every pull request adds a line under **Unreleased**
(Added / Changed / Fixed / Removed), so a regression can be traced to the change that introduced it.

## [Unreleased]

### Changed
- Engine architecture (ADR 0004, `CONTEXT.md`): one `ChangeContext` per change (`Engine.change()`), a pure selection
  policy (`selection.choose()`), a calibration ledger (`risk/ledger.py`), read models for the API (`views.py`) and
  Python described by a language spec like every other language. Decisions and API answers are unchanged; the
  working tree is parsed once per decision instead of up to six times. `Engine.analyse()` and
  `Engine.without_runtime_evidence()` are removed; `Engine.change()` returns a `ChangeContext`.
- The knowledge graph and the co-change features read git history with one reader (`evidence/history.py`).
- No import cycles left in the package (CodeQL `py/cyclic-import`, #94): `.codetwin.toml` templates live in
  `config_templates.py`, `codetwin init` writes the file, the Python mutant moved into the Python adapter, the
  store's legacy import no longer imports the store, and `ChangeContext` is typed against a small `Workspace`
  protocol.
- `Store.decisions()` reads selections and reasons with one query per table instead of two per row
  (`/api/decisions?limit=500` went from about 1,000 queries to 3, #91).

### Added
- `select --json` and `codetwin explain` report `risk_before`, the estimated residual risk of the first selection,
  next to `residual_risk`, the risk of the tests that run (#96).

### Changed
- Isotonic recalibration of risk scores starts only with at least 5 affected and 5 unaffected test examples from
  `codetwin learn`; before that the model's scores are used as they are and `select` says so. A fit on a few points
  used to report 0.0% residual risk (#99).
- `record` stores a run that did not complete (whole-run timeout; pytest exit codes 2, 3, 4) with a warning, and
  `select` never picks it as the default base (a base named with `--base` is used, with a note); `record` then
  exits 1 (#99).

### Fixed
- Co-change evidence was always empty: `git log --format=@@` is not a valid format, and the error was ignored. It now
  works, reads history only up to the recorded base commit (E5), and a shallow clone or missing history is stated in
  the decision's reasons (#99).
- `record` stores the run and the static facts in one transaction (E6); the store uses SQLite WAL and a 5 s busy
  timeout, so the CLI, the server and the VS Code extension can share it (#99).
- A corrupt `.codetwin/model.json` gives a clear error instead of a raw JSON traceback (#99).
- The stored risk of a decision now describes its stored selection: an abstention to a broader selection keeps
  both risks and states both in its reason (E1), and the override to every test for files without runtime evidence
  recomputes the risk (E2) (#96).
- A change that edits only tests is stored (mode `no-source-change`), so `run`, `learn` and `explain` no longer use
  an older decision; `learn` stores its outcome without changing calibration (E3) (#96).
- The report sections (`extras`) of a decision are stored, so `explain` shows them later (E4, migration 0005) (#96).
- `codetwin run --decision FILE` runs the tests of that `select --json` file; the GitHub Action uses it. A change
  that edits only tests is printed but not stored, so the Action used to run an older decision's tests or none.
- `codetwin learn` stores its label in one transaction, so a run that stops part way can simply be repeated.
- A migration script that fails part way is rolled back.
- `codetwin review` places inline comments only on lines of the pull request's own diff (its base commit from the
  workflow event), not of the diff against an older recorded commit. When that commit is not in the checkout (a
  shallow clone), it falls back to the recorded diff.
- `/api/decisions` returns empty lists, not null, for a decision without selected tests or reasons.

## [0.2.0] - 2026-11-18

Any repository in any language, pull-request review, a code knowledge graph, a normalized evidence store, the
cloud plane (API, uploads, self-hosting) and a redesigned dashboard with a hosted demo.

### Added
- Dashboard redesign: design tokens with a light and dark theme toggle, sidebar layout, residual-risk gauge, sparklines
  and outcome donut on the overview, filterable decisions with expandable rows, area chart of the observed miss rate
  against the target, skeleton, empty and error states. New pages: interactive dependency graph (search, hover
  highlight, details panel), repository analysis (hub files, files without a test, unresolved links) and a decision
  detail page; plain-language help tips throughout. Reads the same API; no engine change.
- Self-hosting: `compose.yaml` (Postgres, cloud API, dashboard), Dockerfiles for the API (non-root, health
  check) and the dashboard (nginx), `docs/self-hosting.md`; CI job `self-host` runs the stack end to end
- `codetwin push`: uploads the decision report to CodeTwin Cloud (GitHub OIDC in Actions, project token when
  self-hosting; https only except localhost; `--dry-run` prints what is sent; `--best-effort` never fails CI).
  Report sections opt in with `PUBLISH = True`. Action inputs `upload` and `upload-server`
- Cloud API (`cloud/`, package `codetwin-cloud`): uploads authenticated with GitHub OIDC (or project tokens
  when self-hosting), strict `codetwin.report/v1` validation, idempotent storage in Postgres, read endpoints with
  the local API's shapes (contract test), 90-day retention cron, operator commands; CI job `cloud` with Postgres
- Contributor process (`AGENTS.md`, `CONTRIBUTING.md`, pull request template): every AI coding tool uses its
  matching skills and self-reviews the whole change right after opening a pull request, before asking for review
  (Claude Code `/code-review`, Codex `/review`, or a checklist); the code owner runs `/code-review` before every
  merge, with at most two re-runs after fixes; the rule against
  hard-coded languages and repositories is listed with the project rules.
- Cloud design: ADR 0003 (a cloud plane that receives decision reports, never code), `docs/cloud.md`
  (report format, API, OIDC uploads, schema, environments, operations) and `docs/data-policy.md`
- Hosted dashboard: a demo mode (`npm run dev:demo`, `build:demo`) reads a snapshot of the API written by
  `scripts/demo_snapshot.py` from a real engine run on `examples/python`; Vercel config (`dashboard/vercel.json`);
  CI job `dashboard-demo` checks the deployment build on every pull request; guide in `docs/dashboard.md`
- `codetwin gaps [--json]`: print the test-gap report (changed lines no recorded test ran) without storing a decision; consecutive lines are merged into ranges in the text output. Exits 2 with the message on stderr when nothing is recorded, and 1 when the section fails (same `error` shape as in `select`).
- Dashboard server endpoints: `GET /api/decisions/{id}` (single decision with selection reasons, per-test risk scores and outcome), `GET /api/flaky` (flaky tests grouped by test and sorted by failure count), and `GET /api/kg` (code knowledge graph with node/edge shapes, `?symbols=false` filtering, and cache).
- Typed client models in `dashboard/src/lib/api.ts` (`DecisionDetail`, `FlakyTest`, `KgNode`, `KgEdge`, `KnowledgeGraph`).
- Report section `test_gaps` (`src/codetwin/report/test_gaps.py`): reports changed lines that ran under no test before the change, mapping them to enclosing symbols and working-tree line numbers.
- `codetwin review`: pull-request review from evidence. Analyzers (one file each, `review/analyzers/`) turn the
  decision into findings at file and line with stable rule ids CT001–CT006 (abstention, untested changed symbol,
  dynamic calls, breaking contract, affected connected repository, file without evidence) and an optional,
  advisory LLM reviewer (CT100, `--llm`) that gets graph context, is capped at medium severity and can never block.
  Output as a Markdown PR comment, GitHub inline review, SARIF 2.1.0 or JSON; `--post-github` updates one summary
  comment per pull request and never repeats an inline comment. The GitHub Action posts it with `review: "true"`.
  Guide: docs/review.md.
- `codetwin kg`: code knowledge graph (`src/codetwin/kg/`) of files, tests, symbols and unresolved links with
  typed evidence edges (imports, covers, co-changes, defines), built from the evidence store; blast radius of a
  change; GraphML and node-link JSON export. Guide: docs/knowledge-graph.md.
- Repository standards: CodeQL and OpenSSF Scorecard workflows, `CODE_OF_CONDUCT.md`, `CITATION.cff`, and
  architecture decision records (`docs/adr/`).
- Language adapters (`src/codetwin/lang/`): any language, not only Python. A generic tree-sitter adapter gives
  static facts (dependencies, dynamic constructs, function spans, load-time code), semantic no-op detection and
  weakcheck mutants; each test file runs on its own with the project's test runner and any of five coverage
  formats (LCOV, Go, JaCoCo, Cobertura, Clover). Specs with import resolution and runner presets for
  JavaScript/TypeScript, Go, Java, Kotlin, Rust, C#, Ruby, PHP and C/C++; other languages via `[language]` and
  `[runner]` in `.codetwin.toml`. `codetwin init` detects the language and runner (`--language` to choose).
  Python results are unchanged (same decisions, selections and report sections as before). Guide:
  docs/languages.md.
- Any repository: languages without a spec get rules built from their tree-sitter grammar; repositories with
  several languages are handled together (`languages = [...]`, one `[lang.<name>]` table each); each test runs
  from its nearest project folder with that folder's runner (monorepos); Python inside a larger repository
  finds its import roots; without a test runner CodeTwin works on static evidence and every affected
  decision abstains and says why. Weakcheck mutants for C#, Ruby, PHP, Rust, C/C++ and Kotlin.
- VS Code extension: activates in every folder, works on every file type, and offers to set up a repository
  that has no `.codetwin.toml` (`codetwin init` + `codetwin record`).
- CI job `languages`: every feature on sample repositories (`examples/`) for Python, JavaScript, TypeScript,
  Go, Java, C#, Rust, Ruby, PHP, C++, an unknown language (Lua) and a mixed repository, each with its real
  toolchain (`scripts/language_smoke.py`).

### Changed
- tree-sitter and its grammars are regular dependencies, so `pip install codetwin` supports every language.
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
  to find functions that are executed but not checked. Test files that already fail without the mutation are
  run first and left out (`baseline_failures`); functions in added files are reported as `untested`; one-line
  functions keep their header; an unrecorded `--base` is a clear error.
- `codetwin learn` labels the change-level features of the decision it learns from (`change_points`), and only
  when they were computed for that saved decision.

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

[Unreleased]: https://github.com/aaryagodbole/CodeTwin/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/aaryagodbole/CodeTwin/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aaryagodbole/CodeTwin/releases/tag/v0.1.0
