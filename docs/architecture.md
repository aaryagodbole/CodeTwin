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
