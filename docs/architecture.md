# Architecture

```
            ┌──────────────── Layer 4: interfaces ────────────────┐
            │ CLI (codetwin) · VS Code extension · GitHub Action · │
            │ MCP server for AI agents                             │
            └───────────────┬──────────────────────────────────────┘
                            │ Engine (codetwin.engine)
  Layer 3  risk.features → risk.model → selection (budget | calibrated) → risk.residual → proceed/abstain
                            │                    ▲ risk.calibration (CRC + ACI), learns from `codetwin learn`
  Layer 2  store.db (SQLite: runs, static facts, decisions, outcomes, state) · graph.impact (NetworkX)
                            │
  Layer 1  evidence.diff (git) · evidence.static (ast) · evidence.coverage (pytest + coverage.py contexts)
```

## Data flow of `codetwin select`

1. Load the recorded run of the base commit (coverage per test file, run times, import-time lines).
2. Diff base → working tree; compute static facts of the working tree.
3. Compute 7 features per test file (line/function/file coverage, import distance, name match, co-change, changed test).
4. Score with the risk model (prior weights until trained), choose the threshold with conformal risk control
   at the adaptive level α_t (or fill a time budget), estimate r(c), and abstain if r(c) > α.
5. Store the decision. `codetwin learn` later runs the full suite, marks whether the selection missed an
   affected test, and updates the calibration set, the isotonic recalibration and α_t.

## Evidence types

static · runtime · declared (planned) · co-change · suggested (planned, LLM) · unresolved.
Unresolved links (e.g. `getattr` with a computed name) are reported as unknowns, never treated as "no dependency".

## Extension points (how to add a feature without editing shared files)

Four people build features in parallel, so every feature goes into its **own file**, which is discovered
automatically. Shared files (`cli.py`, `mcp_server.py`, `engine.py`, `store/db.py`, `config.py`,
`extension.ts`) should almost never change; if your feature seems to need it, discuss it in the PR first.

| You are adding | Put it in | Contract |
|---|---|---|
| a CLI command (`codetwin gaps`) | `src/codetwin/commands/<name>.py` | `NAME`, `HELP`, `ORDER`, `add_arguments(p)`, `run(args)` |
| an MCP tool (`close_gap`) | `src/codetwin/mcp_tools/<name>.py` | `register(mcp, root)` with `@mcp.tool()` |
| data in every decision (test gaps, blind spots, evidence cards, freshness) | `src/codetwin/report/<name>.py` | `NAME`, `contribute(ctx) -> dict` with a `"summary"`; appears under `extras.<NAME>` in `select --json`, MCP and VS Code |
| a database table or column | `src/codetwin/store/migrations/NNNN_<name>.sql` | applied once, tracked by file name; never edit an applied file |
| settings for your feature | your own table in `.codetwin.toml`, e.g. `[crossrepo]` | read with `cfg.section("crossrepo")`; no change to `config.py` |
| a larger module | its own package: `crossrepo/`, `contracts/`, `server/`, `llm/` | purpose and status in the package docstring |
| an editor feature (F1–F11) | `extensions/vscode/src/features/<name>.ts` | export a `Feature`, add one line to `features/index.ts`; react to `ctx.onDidDecide` |
| the web dashboard | `dashboard/` (front end) and `src/codetwin/server/` (API) | front end reads only the API |

Report sections only read the `report.Context` (pre-change evidence; no look-ahead) and must not change the
selection or the decision. A section that raises is shown as `{"error": ...}`, never dropped silently.
The JSON contract is described in [output.md](output.md).
