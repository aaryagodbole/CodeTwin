# AGENTS.md

How everyone works in this repository: team members and AI coding agents follow the same steps. New to git or
GitHub? Start with "Step by step for beginners" below. Background: README.md and CONTRIBUTING.md.

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

## Step by step for beginners (exact commands)

The same workflow as the next section, as commands to copy. Run them in Git Bash (Windows) or a terminal (macOS,
Linux), from the repository folder. Replace the parts in `<...>`.

**Once, on a new computer**

```bash
git clone https://github.com/aaryagodbole/CodeTwin.git && cd CodeTwin
python -m venv .venv && source .venv/bin/activate     # Windows Git Bash: source .venv/Scripts/activate
pip install -e ".[dev,mcp,server]"
scripts/check.sh                                       # should pass before you change anything
```

**1. Start a task (every new issue)**

```bash
git checkout dev
git pull                                               # get everything merged so far
git checkout -b feature/<branch-name-from-the-issue>
```

Read the issue and its comments first. If you want to do anything differently, comment on the issue and wait.

**2. Every time you sit down to work again**

```bash
git fetch origin
git log --oneline HEAD..origin/dev                     # empty = you are up to date
git merge origin/dev                                   # only if the line above printed commits
```

If the merge says `CONFLICT`, see "Merge conflicts" in step 3 of the workflow below. To stop a merge you
are unsure about: `git merge --abort` (nothing is lost), then ask on the pull request.

**3. Save your work (often, in small steps)**

```bash
git status                                             # what changed; never commit .codetwin/, node_modules/, out/
git add <files you changed>                            # name the files; avoid `git add .`
git commit -m "Add <what this commit does>"            # imperative: "Add", "Fix", "Update"
git push -u origin HEAD                                # first push; afterwards just `git push`
```

**4. Before opening the pull request**

```bash
git fetch origin && git merge origin/dev               # latest dev again
scripts/check.sh                                       # must pass; fix every error it prints
```

Add a line to `CHANGELOG.md` under *Unreleased*, and update the docs the issue names.

Then **review your own change** before anyone else does: see "Self-review before opening a pull request" below.
Fix what it finds, run `scripts/check.sh` again, and repeat until the review finds nothing new.

**5. Open the pull request**

```bash
gh pr create --base dev --fill                         # or use the "Compare & pull request" button on GitHub
```

Fill in every part of the template: `Closes #<issue>`, the checklist, *Beyond the issue* (write "none" if you
followed the issue exactly), *Self-review* (what your review found and what you fixed) and a screenshot for a
dashboard or VS Code change. Do not open it as a draft
unless you are still working; drafts are not reviewed.

**6. Wait for CI (the checks at the bottom of the pull request)**

- Green tick: go on.
- Red cross: click *Details* next to the failed check, scroll to the first red error line, fix it locally,
  run `scripts/check.sh`, commit and push. Don't ask for reviews while checks are red.
- If a check fails in code you did not touch, merge the latest `dev` first (step 2); if it still fails, say so
  on the pull request instead of changing unrelated code.

**7. Ask for reviews**

1. Optional, any time: ask PR-Agent (see below).
2. When checks are green: comment `@coderabbitai full review`. Wait for its review (a few minutes).
3. The code owner (Aarya) is requested automatically, and runs a full code review (`/code-review` in Claude
   Code) on every pull request before it can be merged. Its findings arrive as review comments; answer them in
   step 8 like any other.

**PR-Agent: the free AI reviewer you can use as often as you like**

PR-Agent runs on the project's Gemini key (model `gemini-3.8-flash`). It never runs by itself. You ask by
writing a new comment on your pull request (the box at the bottom of the *Conversation* tab), with the
command at the very start of the comment:

| Write this comment | What you get |
|---|---|
| `/review` | a review: possible bugs, security problems, missing tests, with file and line |
| `/improve` | code changes it suggests, each with a *Commit suggestion* button |
| `/describe` | a title and summary of your pull request |
| `/ask "why does select() return -1 here?"` | an answer about your change; put the question in quotes |

- One command per comment, at the start: `/review` works, `please /review` does not.
- It answers in 1 to 3 minutes, as a comment from **github-actions**. You can watch it run in the *Actions*
  tab under "PR-Agent".
- Only team members (people with write access to the repository) can use it. A comment from anyone else is
  ignored.
- After you push fixes, write `/review` again in a new comment to check them.
- Treat its findings like CodeRabbit's: check each one against the code, fix or answer it (step 8). Its
  *Commit suggestion* buttons commit straight to your branch, so pull (`git pull`) before you work on.
- If its comment says it failed (for example a quota or key error), wait a few minutes and try once more, then
  tell Aarya. Don't keep re-posting the command.

**8. Answer every review comment (you, the author, do this yourself)**

The review comments on your pull request are yours to fix, answer and resolve. Reviewers (Aarya, CodeRabbit,
PR-Agent and AI assistants) only comment; they do not push to your branch or resolve your threads. That is how
you learn the codebase, so don't wait for someone else to fix it. If you are stuck on a comment, reply in that
thread with what you tried and ask.

For each comment from CodeRabbit, PR-Agent or Aarya:

1. Read it, and check it against the code. AI reviewers are sometimes wrong.
2. If it is right: fix it, commit, push, then reply in that thread with "Fixed in `<commit id>`" plus one line
   saying what changed. Find the commit id with `git log --oneline -1`.
3. If it is wrong or out of scope: reply with the reason and evidence (a test, a line of code, the issue text).
4. Click *Resolve conversation* only after your fix is pushed, or after the reviewer agrees.

When all fixes are pushed, comment `@coderabbitai review` once (not after every small push).

**9. Merge and clean up**

Aarya merges (squash) only after the `/code-review` findings are fixed or answered, the other review comments
are resolved and CI is green. Never merge your own pull request. After the merge:

```bash
git checkout dev && git pull
git branch -d feature/<branch-name>                    # delete your local branch
```

Set the Notion card to *Done*, and comment on any issue that was waiting for yours.

**Never**

- `git push --force` / `git push -f`, `git reset --hard` on a pushed branch, or `git rebase` after a review
  started. Reviewers lose their place, and work can be lost. To undo a pushed commit, use `git revert <id>`.
- Commit secrets (API keys, tokens, `.env` files). If you pushed one by mistake, tell Aarya at once; the key
  must be revoked, not only deleted from the file.
- Commit directly to `dev` or `main`, or work on someone else's branch without asking them.
- Add `Co-authored-by` or AI-attribution lines to commits.

**When stuck**

Comment on your pull request or the issue: what you ran, the full error message (copy it as text, not a
screenshot), and what you already tried. Don't wait silently.

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
   Then do the **self-review** (next section) and fix what it finds before opening the pull request.
6. **Open the pull request into `dev`.** Fill in the template:
   - write `Closes #<issue>` in the body
   - list anything you did differently from the issue, and why, with a link to the issue comment where it was
     agreed
   - add a screenshot for any VS Code or dashboard change
7. **Get both reviews.** A pull request is merged only after both:
   - **CodeRabbit.** Auto-review is off in this repository. When the pull request is ready (checks green, your
     own review done), comment exactly `@coderabbitai full review`. This must be a mention, not a link. After
     you have pushed fixes for its comments, comment `@coderabbitai review` once. The free plan allows about one
     review an hour for the whole repository, so do not ask on every push. If it answers "rate limited", wait
     for the time it gives and ask again; do not comment again before that.
   - **PR-Agent** (optional, free, no hourly limit) runs only when asked. Comment `/review` for findings,
     `/improve` for code suggestions, `/describe` for a summary or `/ask "..."` for a question; comment again
     after you push fixes. Rules: `.pr_agent.toml`. Answer its comments like CodeRabbit's.
   - **Code owner.** `.github/CODEOWNERS` requests Aarya automatically. Don't merge your own pull request.
   - **`/code-review` before every merge.** No pull request is merged without a `/code-review` (Claude Code) run
     on its latest commit, even when CodeRabbit and PR-Agent found nothing. The reviewer reads the linked issue
     first, so a finding that is really a problem in the issue's Approach is raised on the issue, not blamed on
     the author.
8. **Resolve every review comment yourself**, from CodeRabbit, PR-Agent and the code owner. The author of the pull
   request fixes and resolves; reviewers only comment. For each one, either:
   - fix it, push, and reply with what you changed (commit id), or
   - explain why not (out of scope, conflicts with the issue, a false alarm), with evidence.

   Resolve a conversation only when it is fixed or the reviewer agrees. Push new commits; don't force-push over
   reviewed commits. When all conversations are resolved and CI passes, ask Aarya to merge. If you pushed after
   the last `/code-review`, say so: the review runs again on the latest commit before the merge.
9. **After merging**, set the Notion card to Done and comment on any issue that was waiting for yours.

AI assistants follow the same steps. In particular: post the step 2 plan on the issue before writing code beyond
what the issue says, and never resolve a reviewer's conversation without a fix or an agreed reason. When an AI
assistant reviews someone else's pull request, it only posts comments: it does not push to that branch or
resolve its threads, unless the code owner asks for it on that pull request.

## AI coding tools: use your skills

Most AI coding tools come with skills, slash commands, rules, workflows or plugins for common jobs: Claude Code
skills and slash commands, Codex skills and prompts, Antigravity workflows and rules, Cursor rules, Copilot
prompts. They encode a better process than an ad-hoc attempt. An AI tool working in this repository must:

1. **Look first.** At the start of each task, list the skills and commands it has (for example `/help` or its
   skill list), and read the description of any that might fit.
2. **Use the matching one** whenever a skill exists for the job, instead of doing it by hand:

   | Job | Kind of skill or command to use |
   |---|---|
   | Plan a change, design an interface, restructure code | planning, design or architecture skill |
   | Write a feature or fix a bug test-first | TDD (test-driven development) skill |
   | A failing test, a crash, wrong output, slow code | debugging or diagnosis skill |
   | Review a change (self-review, someone's pull request) | code review skill (`/code-review`, `/review`) |
   | Security-sensitive code (auth, uploads, secrets, workflows) | security review skill |
   | Simplify or clean up code you wrote | simplify or refactor skill |
   | Dashboard or VS Code UI | frontend, design or accessibility skill |
   | Commit messages, pull request text | commit or pull-request skill |
   | Docs, CHANGELOG, explanations | documentation skill |

3. **Say which it used.** Name the skill or command in the pull request's *Self-review* section, or in the
   issue comment for a plan, so reviewers know how the work was checked.
4. **Rules still win.** A skill never overrides this file: the project rules below, the issue's Approach and
   the review steps apply whatever a skill suggests. If they conflict, follow this file and say so on the issue.

If a tool has no skill for a job, follow the steps in this file by hand.

## Self-review before opening a pull request

Every author does this, and every AI coding tool (Claude Code, Codex, Antigravity, Copilot, Cursor or any
other) must do it before it opens or updates a pull request. A pull request without a self-review is not ready
for review.

**1. Run a full review of your whole change** against the latest `dev` (`git fetch origin`, then review
`git diff origin/dev...HEAD`, not only the last commit):

| Tool | How |
|---|---|
| Claude Code | `/code-review` |
| Codex | `/review`, against the base branch `dev` |
| Any other tool or agent (Antigravity, Copilot, Cursor, ...) | ask it to review `git diff origin/dev...HEAD` using the checklist below, and to list each problem with file, line and a concrete failing input |
| No AI tool | go through the checklist below yourself, file by file |

**2. The checklist** (what the review must look for):

1. **The issue.** Does the change do exactly what the issue's Approach and Done-when say, no more and no less?
   If the Approach itself looks wrong, comment on the issue instead of silently changing it.
2. **Correctness.** For each finding, a concrete input and the wrong output: empty input, missing files,
   `None`/NaN, errors from git or the store, a very large repository, a second run, Windows paths.
3. **Project rules** (next section): no look-ahead, unknowns reported, no hard-coded language or repository,
   output contract, layering, extension points.
4. **Errors and output.** Errors go to stderr with the CLI's exit codes; `--json` prints only valid JSON on
   stdout; messages are short and say what to do.
5. **Security.** Input from users, uploads, LLMs and the network is validated; no secrets in code, logs or
   output; no `${{ ... }}` inside workflow shell code; credentials only over HTTPS.
6. **Tests.** Every new behaviour and every fixed bug has a test, and that test fails without your change.
7. **Duplication and size.** No copied blocks that must be kept in step; reuse existing helpers.
8. **Docs.** CHANGELOG, README and `docs/` match the new behaviour.

**3. Fix and repeat.** Fix every real finding, run `scripts/check.sh`, and review again until nothing new
comes up. A finding you think is wrong: keep a one-line reason.

**4. Report it** in the pull request's *Self-review* section:
- the tool you used
- what the review found
- what you fixed, with commit ids
- what you did not change, and why

The code owner still runs `/code-review` before merging. A self-review makes that review short; it does not
replace it.

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
