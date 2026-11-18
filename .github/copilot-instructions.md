# Review instructions for GitHub Copilot

CodeTwin AI selects regression tests, estimates the risk left by a selection and abstains when the
evidence is weak. Its behaviour is fixed by a research paper, so reviews should check these rules first
(full list: `AGENTS.md`; PR-Agent gets the same rules from `.pr_agent.toml`).

## Flag as a problem

- **Look-ahead.** Code in `src/codetwin/risk/`, `selection.py` or `report/` that uses the *new* test run
  (anything only known after the change's tests ran). Only `Engine.learn()` may use it, to build the ground truth.
- **Dropped unknowns.** Unresolved links (dynamic calls such as `getattr` with a computed name, unparsed files,
  new modules) silently treated as "no dependency" instead of being reported in `Impact.unknowns` or
  `Decision.reasons`.
- **Calibration semantics changed.** `crc_threshold` must return `-1.0` when no threshold is feasible (select
  every test); the adaptive level is updated only after an outcome is known; abstain when the residual risk is
  above the target. Report sections must not change the selection or the decision.
- **Hard-coded languages or repositories.** CodeTwin must work on any repository in any language. Flag new
  special cases for one language, file extension, test runner or repository name in shared code. Language facts
  belong in `src/codetwin/lang/specs/` or `.codetwin.toml`, and runners are detected, not assumed.
- **Output contract.** Changes to top-level keys of `Decision.to_dict()` without an `OUTPUT_SCHEMA` bump.
- **Layering.** Analysis logic in `extensions/`, `action/` or `dashboard/`, or features added by editing
  `cli.py`, `mcp_server.py`, `engine.py` or `extension.ts` instead of the auto-discovered extension folders.
- **LLM code** (`llm/`) that changes a selection, a decision, a risk number or the evidence store, or that
  logs or returns API keys.
- **Resources and safety.** Engines or stores not closed (`with Engine(...)`), shell code in workflows or
  `action/` that interpolates `${{ ... }}` or file names instead of passing them through `env:`.
- **Numbers.** Hand-edited numbers in the paper, synopsis or README; they come from scripts.
- **Tests.** New behaviour without a test; tests that depend on network access.

## Style

Python 3.12+, type hints, `ruff` clean, small functions, docstrings that say *why*. Prefer clear names over
comments. Keep user-facing messages short and specific.
