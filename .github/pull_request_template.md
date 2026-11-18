## What and why

<!-- One or two sentences. Link the issue or task. -->

## Layer

- [ ] evidence  - [ ] store/graph  - [ ] risk/selection  - [ ] CLI/MCP  - [ ] VS Code  - [ ] Action  - [ ] docs

## Checklist

- [ ] `scripts/check.sh` passes (lint, tests, coverage threshold, extension build)
- [ ] Line added to `CHANGELOG.md` under Unreleased
- [ ] New behaviour has a test
- [ ] No look-ahead: decisions use only evidence from before the change's tests run
- [ ] Unresolved links are reported, not dropped
- [ ] README/docs updated if commands or behaviour changed

## Beyond the issue

<!-- Anything done differently from, or in addition to, the issue's Approach, and why.
     Link the issue comment where it was agreed. Write "none" if you followed the issue exactly. -->

## Self-review (see AGENTS.md, "Self-review of your pull request")

<!-- Tool used (Claude Code /code-review, Codex /review, Antigravity, ... or by hand), and any other skills
     or commands you used for this change (TDD, debugging, security review, ...).
     What the review found, what you fixed (commit ids), and what you left and why. -->

## Reviews (see AGENTS.md, "Step by step for beginners")

- [ ] Merged the latest `dev` into this branch before asking for review
- [ ] Checks are green
- [ ] Commented `@coderabbitai full review` once ready (and `@coderabbitai review` once after pushing fixes)
- [ ] Code owner review requested (automatic via CODEOWNERS)
- [ ] Every review comment fixed or answered with a reason; conversations resolved only when done
- [ ] Screenshot added (VS Code or dashboard changes)

## Before merge (code owner)

- [ ] Merge review: `/code-review --comment <pull request number>` on the latest commit; every finding fixed or answered
