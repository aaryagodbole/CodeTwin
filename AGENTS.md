# AGENTS.md

Instructions for AI coding agents working in this repository. Humans: see README.md and CONTRIBUTING.md.

## Commands

```bash
pip install -e ".[dev,mcp,server]"            # once, from the repository root
scripts/check.sh                       # the definition of done: ruff + pytest + extension build
python -m pytest tests/test_risk.py    # one file; tests need `git` on PATH (they create throwaway repos)
cd extensions/vscode && npm ci && npm run compile
cd dashboard && npm ci && npm run dev    # needs `codetwin serve` running in a project
```

A change is done only when `scripts/check.sh` passes (ruff, mypy, pytest with coverage, extension and dashboard
builds) and new behaviour has a test.

## Workflow: from issue to merged pull request

Every task is a GitHub issue assigned to one person. The issue's **Approach** and **Done when** sections are the
spec. Follow these steps in order.

1. **Read the issue completely**, including its comments. Also read every file it names under *Background*. If the
   issue says *Start after* another issue, check that issue is merged (or open as a PR, if that is what it says)
   before you begin.
2. **Plan before you code.** If you see a gap, a bug in the approach, a simpler way, or something worth adding,
   **write it as a comment on the issue first**. Say:
   - *what* you want to change or add
   - *why*, with a concrete example: an input and the wrong or better output
   - *what it affects*: files, output keys, other people's tasks

   Wait for Aarya's reply before building anything beyond the issue. Small things that only make the issued work
   more correct may go ahead, but still need the comment. Never silently do more or less than the issue says.
3. **Branch** from up-to-date `dev`: `git checkout dev && git pull && git checkout -b <branch named in the issue>`.
   Use one branch and one pull request per issue.

   **Always start from the latest `dev`.** Before you start, and again every time you come back to the work, run
   `git fetch origin` and check `git log --oneline HEAD..origin/dev`. If it lists commits, bring them in with
   `git merge origin/dev` before writing more code. Do this again before you open the pull request and before
   asking for a review. Other people's pull requests are merged every day, and working on an old `dev` is how
   conflicts and broken builds happen.

   **Merge conflicts.** Solve a conflict yourself only when it is easy and clear: for example both sides added
   different lines to `CHANGELOG.md` or a list (keep both), or one side only renamed or moved code the other
   side did not touch. Read both sides, keep every change that is meant to stay, then run `scripts/check.sh`
   and say in the pull request which files had conflicts and how you solved them. If a conflict changes logic,
   or you are not sure which side is right, stop: do not guess, and do not delete the other person's work.
   Comment on the pull request which files conflict and ask the code owner (Aarya) to solve them. Never
   force-push to solve a conflict.
4. **Implement exactly the Approach**, plus any additions agreed in step 2. Keep commits small with clear
   messages. Follow the rules below (no look-ahead, unknowns reported, extension points, output contract).
5. **Test what the issue lists**, plus one test for each extra case you added. Try the feature by hand as the
   issue describes. Run `scripts/check.sh` until it passes. Update the CHANGELOG and docs named in the issue.
6. **Open the pull request into `dev`.** Fill in the template:
   - write `Closes #<issue>` in the body
   - list anything you did differently from the issue, and why, with a link to the issue comment where it was
     agreed
   - add a screenshot for any VS Code or dashboard change
7. **Get both reviews.** A pull request is merged only after both:
   - **CodeRabbit.** Auto-review is off in this repository, so comment exactly `@coderabbitai full review` on the
     pull request. This must be a mention, not a link. After each new push, comment `@coderabbitai review`.
     The free plan allows about one review an hour, so ask for it when the pull request is ready, not on every
     push.
   - **Gemini Code Assist** reviews once when the pull request opens (rules: `.gemini/styleguide.md`). Comment
     `/gemini review` for another review after you push fixes. Answer its comments like CodeRabbit's.
   - **Code owner.** `.github/CODEOWNERS` requests Aarya automatically. Don't merge your own pull request.
8. **Resolve every review comment**, from CodeRabbit and the code owner. For each one, either:
   - fix it, push, and reply with what you changed (commit id), or
   - explain why not (out of scope, conflicts with the issue, a false alarm), with evidence.

   Resolve a conversation only when it is fixed or the reviewer agrees. Push new commits; don't force-push over
   reviewed commits. When all conversations are resolved and CI passes, ask Aarya to merge.
9. **After merging**, set the Notion card to Done and comment on any issue that was waiting for yours.

AI assistants follow the same steps. In particular: post the step 2 plan on the issue before writing code beyond
what the issue says, and never resolve a reviewer's conversation without a fix or an agreed reason.

## Rules specific to this project

- **No look-ahead.** Code in `risk/` and `selection.py` may use only evidence that exists *before* a change's
  tests run: the base commit's recorded run, the diff, and static facts of the new code. The new run is used
  only in `Engine.learn()` to compute the ground truth. Using it for features or decisions invalidates the method.
- **Unknown is not "no dependency".** Never drop unresolved links (dynamic calls, unparsed files, new modules);
  report them in `Impact.unknowns` / `Decision.reasons`.
- **Calibration semantics are fixed by the paper.** `crc_threshold` returns `-1.0` when no threshold is feasible,
  which means "select every test". The adaptive level is updated only after an outcome is known
  (`AdaptiveLevel.update`). Abstain when `residual_risk > alpha`. Do not change these without changing the paper.
- **Layering.** The VS Code extension, GitHub Action, MCP server and dashboard call the engine through the CLI,
  `codetwin.engine.Engine` or the read-only API. Never put analysis logic in `extensions/`, `action/` or `dashboard/`.
- **Package manager.** npm for both `extensions/vscode` and `dashboard` (lockfiles committed; CI uses `npm ci`).
- **Extension points.** New commands, MCP tools, report sections, DB migrations and editor features each go in
  their own file (`commands/`, `mcp_tools/`, `report/`, `store/migrations/`, `extensions/vscode/src/features/`);
  they are discovered automatically. Do not edit `cli.py`, `mcp_server.py`, `engine.py` or `extension.ts` to add
  a feature. Feature settings: `cfg.section("<name>")`. Table: `docs/architecture.md`.
- **Output contract.** `Decision.to_dict()` is read by VS Code, the Action and agents (`docs/output.md`). Add data
  as a report section under `extras`; changing top-level keys needs an `OUTPUT_SCHEMA` bump.
- **LLM explains, never decides.** Code in `llm/` and anything calling it may phrase or summarise evidence, but
  must not change a selection, a decision, a risk number or the evidence store. API keys come only from the
  environment; never log or return them.
- **Resources.** Use `with Engine(root) as eng:` (or `with Store(...)`) so database connections are closed.
- **Shell safety.** In workflows and `action/`, pass event and repository values through `env:` and quote them;
  never put `${{ ... }}` or file names into shell code.
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
