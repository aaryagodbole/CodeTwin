# Contributing

* Branches: `main` is stable, `dev` is the integration branch. Work on `feature/<short-name>` branches
  created from `dev` and open a pull request into `dev`.
* Reviews: every pull request needs an approving review from a code owner (`.github/CODEOWNERS`), who also
  merges it. Releases from `dev` into `main` are done by the maintainers. Do not merge your own pull request.
* Every pull request must pass `scripts/check.sh` (same as CI: ruff, pytest, extension build) and add or update
  tests for the change. Optional: `pip install pre-commit && pre-commit install` to lint on every commit.
* Put new code where [docs/architecture.md → Extension points](docs/architecture.md#extension-points-how-to-add-a-feature-without-editing-shared-files)
  says: one file per command, MCP tool, report section, migration or editor feature. Then two people's pull
  requests do not touch the same file. Keep each pull request to one feature.
* Before opening a pull request: `git fetch origin && git rebase origin/dev`, then `scripts/check.sh`.
* Use the pull-request template; AI coding agents follow `AGENTS.md`.
* Step by step, from issue to merge: [AGENTS.md → Workflow](AGENTS.md#workflow-from-issue-to-merged-pull-request).
  In short: follow the issue's Approach, and suggest any change or addition **on the issue first**, with a reason.
  Before opening the pull request, review your own change with your AI tool (Claude Code `/code-review`, Codex
  `/review`, or the checklist in [AGENTS.md → Self-review](AGENTS.md#self-review-before-opening-a-pull-request))
  and report it in the template's Self-review section. Then get a CodeRabbit review (comment
  `@coderabbitai full review`) and the code owner's review, which includes a `/code-review` run before every
  merge, and fix or answer every comment before merging. For more AI review between CodeRabbit's hourly reviews, comment `/review`
  or `/improve` (PR-Agent).
* Keep the layers separate: the VS Code extension, GitHub Action and MCP server call the engine through the
  CLI or `codetwin.engine.Engine`; analysis code lives only in `src/codetwin`.
* Never claim a number in the README, synopsis or paper that does not come from a script output.
* Commit messages: imperative mood, one topic per commit (e.g. "Add function-level CodeLens").
