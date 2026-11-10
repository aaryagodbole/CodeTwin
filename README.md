# CodeTwin AI

[![CI](https://github.com/aaryagodbole/CodeTwin/actions/workflows/ci.yml/badge.svg)](https://github.com/aaryagodbole/CodeTwin/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Evidence-aware, risk-calibrated change verification.**
CodeTwin AI tells you which tests a code change needs, what its analysis cannot see, and how much risk is
left if you run only those tests. When the risk is above the level you chose, it says so and runs a broader set.

Final-year engineering project of Group P6, Department of Computer Science and Engineering (Data Science),
TSSM's Padmabhooshan Vasantdada Patil Institute of Technology, Pune.

---

## Why

Running the whole test suite after every change is slow, and AI coding assistants now produce changes faster
than people can check them. Existing regression test selection tools pick a subset of tests, but they do not
say how likely that subset is to miss a test that the change affects, and they quietly treat dependencies they
cannot resolve (for example `getattr` with a computed name) as "no dependency".

CodeTwin AI adds three things on top of test selection:

| | What you get |
|---|---|
| **Stated risk** | an estimate of the residual risk `r(c)` of each selection: the chance that it misses an affected test |
| **A target you choose** | a miss-rate target `α` (e.g. 10%); the selection threshold is calibrated against it and keeps adapting as the project changes |
| **Honest abstention** | when `r(c) > α` it abstains to a broader run, and it lists what it could not see (dynamic calls, new or unparsed files) |

## Research results

The method was evaluated on **681 code changes of 8 open-source Python projects**, with three ground truths:
per-test coverage, 812 seeded faults that the tests detect, and the published ground truth of NameRTS.

- A threshold calibrated once on older commits **drifted**: at a 10% target it missed affected tests on 17.5% of later changes.
- With **adaptive conformal calibration**, the observed miss rates were 4.5%, 9.3% and 19.9% for targets of 5%, 10% and 20%,
  while saving 39.1% of test time at the 10% target.
- **Abstaining when the estimated risk exceeds the target** caught 26 of the 31 changes on which line-coverage
  selection missed tests (rule-based triggers caught 7), giving 98.2% safe changes while saving 29.7% of test time.
- Honest limits: the learned ranking was not better than a coverage ranking, and plain file-level coverage was
  already safe on these small libraries; CodeTwin's added value is a stated, adjustable risk.

Paper source, scripts and data: branches [`study-v2`](../../tree/study-v2) (scripts and paper) and
[`study-v2-results`](../../tree/study-v2-results) (data, results, figures).

## Installation

Requires Python 3.11+ and `git`. The project you analyse needs a pytest test suite.

From a release (recommended): download the wheel and the `.vsix` from the
[Releases](../../releases) page, then

```bash
pip install "codetwin-X.Y.Z-py3-none-any.whl[mcp,server]"   # CLI, MCP server, dashboard
code --install-extension codetwin-X.Y.Z.vsix                  # VS Code extension
```

From source:

```bash
git clone https://github.com/aaryagodbole/CodeTwin.git
cd CodeTwin
pip install -e ".[mcp,server]"     # add ",dev" for development tools
```

## Quick start

Run these inside the Python project you want to analyse:

```bash
codetwin init          # writes .codetwin.toml with guessed settings; check them
codetwin record        # runs the suite once with per-test coverage on a clean checkout
# ... edit some code ...
codetwin select        # which tests to run, the estimated residual risk, PROCEED or ABSTAIN
```

Example output:

```
decision: PROCEED   estimated residual risk: 3.1%   mode: calibrated
  - estimated residual risk 3.1% <= target 10%
selected 2 test files:
  tests/test_end_to_end.py
  tests/test_risk.py
```

## Commands

| Command | What it does |
|---|---|
| `codetwin init` | create `.codetwin.toml` (source root, packages, tests directory, target α) |
| `codetwin record` | run the full suite with per-test coverage and store it as evidence for the current commit |
| `codetwin select [--alpha 0.05] [--json]` | select tests for the changes since the recorded commit; calibrated mode |
| `codetwin select --budget 0.25` | best tests within 25% of full-suite time, with the risk left behind |
| `codetwin impact FILE...` | tests reached by files, with how each link is known, and unresolved links |
| `codetwin graph FILE [--lines 10-24] [--json]` | impact graph around a file or selected lines (importers, dependencies, tests, unknowns) |
| `codetwin serve` | web dashboard and read-only API on `http://127.0.0.1:8765` |
| `codetwin learn` | run the full suite, record whether the last selection missed a test, update calibration |
| `codetwin explain` | the numbers and reasons behind the last decision |

All commands accept `-C PATH` to run on another repository.

## Configuration

`.codetwin.toml` in the project root:

```toml
[project]
src_root = "src"                 # directory added to PYTHONPATH ("." or "src")
packages = ["mypackage"]         # packages measured by coverage
source_dirs = ["src/mypackage"]  # directories with source files
tests_dir = "tests"

[selection]
alpha = 0.10                     # target miss rate
budget = 0.25                    # share of full-suite time in budget mode
aci_gamma = 0.02                 # step size of adaptive calibration
fallback = "file-coverage"       # broader run on abstention: file-coverage | full
```

Evidence is stored locally in `.codetwin/` (add it to `.gitignore`). No code leaves your machine.

## How it works

```
Layer 4  Interfaces      CLI · VS Code extension · GitHub Action · MCP server for AI agents
Layer 3  Risk/decision   7 features → risk model → calibrated threshold (CRC + adaptive) → r(c) → proceed / abstain
Layer 2  Store/graph     SQLite evidence store · typed impact graph (static, runtime, co-change, unresolved)
Layer 1  Evidence        git diff (changed lines) · AST facts · per-test coverage and run times
```

1. **Evidence.** `codetwin record` runs pytest with coverage.py dynamic contexts, so every test file's executed
   lines are known. The AST gives imports, dynamic calls, function spans and lines that run at import time.
2. **Features.** For each test file: did it run a changed line / the changed function / the changed file in the
   recorded version, import distance to the changed module, name match, co-change history, and whether the test
   itself changed. Only evidence from *before* the change's tests run is used.
3. **Selection.** A logistic model scores each test. In calibrated mode the threshold comes from conformal risk
   control on earlier changes; adaptive conformal inference lowers the level after a miss and relaxes it after
   safe changes, so the miss rate tracks the target as the project drifts.
4. **Residual risk and abstention.** `r(c) = 1 − ∏ (1 − p̃ᵢ)` over skipped tests, with isotonic recalibration.
   If `r(c) > α`, CodeTwin abstains and runs the broader file-coverage selection (or the full suite).
5. **Learning.** `codetwin learn` runs the full suite (e.g. nightly or after merge), checks whether the selection
   missed an affected test, and updates the calibration set, recalibration and adaptive level.

Details: [docs/architecture.md](docs/architecture.md).

## Integrations

**VS Code** – `extensions/vscode`: select code (or put the cursor in a function) and run
*CodeTwin: Show impact graph of selection* (right-click, `Ctrl+Alt+I`): a graph opens beside the editor with the
files that import it, its dependencies, the tests that execute the selected lines and the links that cannot be
followed, each edge styled by how it is known. Hovering a function shows `used by N · M tests · K unknown`.
Also: *Select tests for my change*, *Record evidence*, *Explain last decision*; the status bar shows the decision
and risk. Develop with `npm ci && npm run compile`, then press F5.

**Web dashboard** – `dashboard/` (Next.js): overview, system map, decisions, results (observed miss rate vs
target) and the impact graph of any file. `codetwin serve` serves it with the API; see
[dashboard/README.md](dashboard/README.md).

**GitHub Actions** – `action/`: on a pull request, records evidence on the base branch, selects tests for the PR,
writes the decision and risk to the job summary and runs the selected tests:

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- uses: actions/setup-python@v5
  with: { python-version: "3.12" }
- uses: aaryagodbole/CodeTwin/action@main
  with: { alpha: "0.10" }
```

**AI coding agents (MCP)** – `codetwin-mcp` exposes `verify_change`, `get_impact`, `get_graph`,
`recommend_tests` and `explain_decision`, so an agent can ask before it opens a pull request. Setup: [docs/mcp.md](docs/mcp.md).

## Project structure

```
src/codetwin/
  evidence/          diff, static facts, per-test coverage                     (Layer 1)
  store/             SQLite evidence store + migrations/*.sql                  (Layer 2)
  graph/             typed impact graph                                        (Layer 2)
  risk/              features, model, calibration, residual risk               (Layer 3)
  selection.py       budget/threshold selection, proceed/abstain, output       (Layer 3)
  report/            sections added to every decision (one file each)
  commands/          CLI commands (one file each)
  mcp_tools/         MCP tools for AI agents (one file each)
  server/            read-only HTTP API for the dashboard
  crossrepo/ contracts/ llm/   planned modules (see docs/roadmap.md)
  engine.py, cli.py, mcp_server.py, config.py, plugins.py   shared core
tests/               unit tests and end-to-end tests on throwaway git repositories
extensions/vscode/   VS Code extension; src/features/ has one file per editor feature
dashboard/           web dashboard (Next.js), served by `codetwin serve`
action/              GitHub composite action
docs/                architecture (incl. extension points), output contract, roadmap, MCP setup
scripts/check.sh     lint + tests + extension build (the definition of done)
AGENTS.md            instructions for AI coding agents working on this repository
```

New features never edit the shared core: see
[docs/architecture.md → Extension points](docs/architecture.md#extension-points-how-to-add-a-feature-without-editing-shared-files).

## Development

```bash
pip install -e ".[dev,mcp,server]"
scripts/check.sh
```

Work on `feature/<name>` branches from `dev` and open a pull request into `dev`; see
[CONTRIBUTING.md](CONTRIBUTING.md). CI runs lint, tests with a coverage gate, a package build with a smoke test,
and the extension and dashboard builds on every pull request. Releases: [docs/releasing.md](docs/releasing.md);
changes: [CHANGELOG.md](CHANGELOG.md). The repository uses CodeTwin on itself (`.codetwin.toml`).

## Roadmap

| Status | Work |
|---|---|
| done | Engine, CLI, MCP server; VS Code impact graph of a selection; web dashboard; Action skeleton; CI and releases; research study and paper |
| next | Test gaps, blind spots and evidence cards; symbol-level impact and CodeLens; PR comment; trained per-project models |
| later | PR comment and merge gate; agent-in-the-loop demo; cross-repository evidence; second language adapter; verified LLM link suggestions |

Full plan: [docs/roadmap.md](docs/roadmap.md).

## License

[MIT](LICENSE)
