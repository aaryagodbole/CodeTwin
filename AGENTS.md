# AGENTS.md

Instructions for AI coding agents working in this repository. Humans: see README.md and CONTRIBUTING.md.

## Commands

```bash
pip install -e ".[dev,mcp]"            # once, from the repository root
scripts/check.sh                       # the definition of done: ruff + pytest + extension build
python -m pytest tests/test_risk.py    # one file; tests need `git` on PATH (they create throwaway repos)
cd extensions/vscode && npm install && npm run compile
```

A change is done only when `scripts/check.sh` passes and new behaviour has a test.

## Rules specific to this project

- **No look-ahead.** Code in `risk/` and `selection.py` may use only evidence that exists *before* a change's
  tests run: the base commit's recorded run, the diff, and static facts of the new code. The new run is used
  only in `Engine.learn()` to compute the ground truth. Using it for features or decisions invalidates the method.
- **Unknown is not "no dependency".** Never drop unresolved links (dynamic calls, unparsed files, new modules);
  report them in `Impact.unknowns` / `Decision.reasons`.
- **Calibration semantics are fixed by the paper.** `crc_threshold` returns `-1.0` when no threshold is feasible,
  which means "select every test". The adaptive level is updated only after an outcome is known
  (`AdaptiveLevel.update`). Abstain when `residual_risk > alpha`. Do not change these without changing the paper.
- **Layering.** The VS Code extension, GitHub Action and MCP server call the engine through the CLI or
  `codetwin.engine.Engine`. Never put analysis logic in `extensions/` or `action/`.
- **Extension points.** New commands, MCP tools, report sections, DB migrations and editor features each go in
  their own file (`commands/`, `mcp_tools/`, `report/`, `store/migrations/`, `extensions/vscode/src/features/`);
  they are discovered automatically. Do not edit `cli.py`, `mcp_server.py`, `engine.py` or `extension.ts` to add
  a feature. Feature settings: `cfg.section("<name>")`. Table: `docs/architecture.md`.
- **Output contract.** `Decision.to_dict()` is read by VS Code, the Action and agents (`docs/output.md`). Add data
  as a report section under `extras`; changing top-level keys needs an `OUTPUT_SCHEMA` bump.
- **MCP SDK.** Support both SDK 1.x (`mcp.server.fastmcp.FastMCP`) and 2.x (`mcp.server.mcpserver.MCPServer`);
  keep the import fallback in `mcp_server.py`.
- **Coverage contexts need the C tracer.** `evidence/coverage.py` sets `COVERAGE_CORE=ctrace`; per-test contexts
  are empty without it. Keep it.
- **Test files can be reported under another file.** pytest's junit file of a test case can differ from the file
  coverage records (inherited test classes). Treat a test as new only if it is in neither `durations` nor `covered`.

## Do not

- Edit numbers in the paper, synopsis or README by hand. Every reported number comes from a script output
  (research code: branch `study-v2`, `pilot/paper_numbers.py`; edit `paper/main.template.tex`, not `main.tex`).
- Commit to `main`, `study-v2`, `study-v2-results` or `paper-v1*`. Work on `feature/<name>` from `dev`, PR into `dev`.
- Add `Co-authored-by` or other AI-attribution trailers to commits, or name an AI tool as author.
- Commit `.codetwin/` (local evidence database) or anything under `node_modules/` or `out/`.
