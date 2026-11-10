# CodeTwin AI

**Evidence-aware, risk-calibrated change verification.** CodeTwin selects the tests a code change needs,
shows what the analysis cannot see, estimates the risk left behind, and runs a broader set when that risk is
above your target. Final-year project of Group P6, Dept. of CSE (Data Science), TSSM's PVPIT, Pune
(guide: Dr. T. A. Kamble).

> The research study behind the paper lives on the `study-v2` branch (scripts) and `study-v2-results`
> (data and results). This branch (`dev`) is the product.

## Quick start

```bash
pip install -e ".[dev,mcp]"          # in this repository
cd /path/to/your/python/project
codetwin init                        # writes .codetwin.toml (check the guessed settings)
codetwin record                      # run the suite once with per-test coverage (clean checkout)
# ... edit code ...
codetwin select                      # tests to run, estimated residual risk, proceed/abstain
codetwin select --budget 0.25        # best tests within 25% of full-suite time
codetwin impact src/pkg/module.py    # tests reached by a file and how each link is known
codetwin learn                       # after a full run: update calibration from the true outcome
codetwin explain                     # evidence behind the last decision
```

## How it works

| Layer | Package | What it does |
|---|---|---|
| 1. Evidence | `codetwin.evidence` | git diff (changed lines), static facts (imports, dynamic calls, function spans, import-time lines), per-test coverage and run times |
| 2. Store and graph | `codetwin.store`, `codetwin.graph` | SQLite evidence store; typed impact graph (static, runtime, unresolved links) |
| 3. Risk and decision | `codetwin.risk`, `codetwin.selection` | 7 features → risk model → budget or calibrated selection (conformal risk control + adaptive conformal inference) → residual risk r(c) → proceed or abstain |
| 4. Interfaces | `codetwin.cli`, `codetwin.mcp_server`, `extensions/vscode`, `action/` | CLI, MCP server for AI agents, VS Code extension, GitHub Action for pull requests |

The decision rule follows the paper: abstain to a broader run (file coverage or the full suite) when the
estimated residual risk exceeds the target α; the threshold adapts after every observed outcome (`codetwin learn`).

## Repository layout

```
src/codetwin/        Python engine, CLI and MCP server
tests/               pytest suite (unit + end-to-end on a throwaway git repo)
extensions/vscode/   VS Code extension (TypeScript) – calls the CLI
action/              GitHub composite action for pull requests
docs/                architecture and roadmap
```

## AI agents (MCP)

`codetwin-mcp` starts a stdio MCP server with the tools `verify_change`, `get_impact`, `recommend_tests` and
`explain_decision`. Set `CODETWIN_ROOT` to the repository to analyse.

## Development

```bash
pip install -e ".[dev,mcp]" && ruff check src tests && python -m pytest
cd extensions/vscode && npm install && npm run compile
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/roadmap.md](docs/roadmap.md).
