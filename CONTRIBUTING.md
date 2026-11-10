# Contributing

* Branches: `main` is stable, `dev` is the integration branch. Work on `feature/<short-name>` branches
  created from `dev` and open a pull request into `dev`.
* Every pull request must pass CI (ruff, pytest, extension build) and add or update tests for the change.
* Keep the layers separate: the VS Code extension, GitHub Action and MCP server call the engine through the
  CLI or `codetwin.engine.Engine`; analysis code lives only in `src/codetwin`.
* Never claim a number in the README, synopsis or paper that does not come from a script output.
* Commit messages: imperative mood, one topic per commit (e.g. "Add function-level CodeLens").
