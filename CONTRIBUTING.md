# Contributing

* Branches: `main` is stable, `dev` is the integration branch. Work on `feature/<short-name>` branches
  created from `dev` and open a pull request into `dev`.
* Every pull request must pass `scripts/check.sh` (same as CI: ruff, pytest, extension build) and add or update
  tests for the change. Optional: `pip install pre-commit && pre-commit install` to lint on every commit.
* Use the pull-request template; AI coding agents follow `AGENTS.md`.
* Keep the layers separate: the VS Code extension, GitHub Action and MCP server call the engine through the
  CLI or `codetwin.engine.Engine`; analysis code lives only in `src/codetwin`.
* Never claim a number in the README, synopsis or paper that does not come from a script output.
* Commit messages: imperative mood, one topic per commit (e.g. "Add function-level CodeLens").
