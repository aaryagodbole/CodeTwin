# CodeTwin AI

[![CI](https://github.com/aaryagodbole/CodeTwin/actions/workflows/ci.yml/badge.svg)](https://github.com/aaryagodbole/CodeTwin/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Evidence-aware, risk-calibrated change verification.**
CodeTwin AI tells you which tests a code change needs, what its analysis cannot see, and how much risk is
left if you run only those tests. When the risk is above the level you chose, it says so and runs a broader set.

Final-year engineering project of Group P6, Department of Computer Science and Engineering (Data Science),
TSSM's Padmabhooshan Vasantdada Patil Institute of Technology, Pune.

---

## Why

Running the whole test suite after every change is slow, and AI coding assistants now produce changes faster
than people can check them. Existing regression test selection tools pick a subset of tests, but they do not
say how likely that subset is to miss a test that the change affects, and they quietly treat dependencies they
cannot resolve (for example `getattr` with a computed name) as "no dependency".

CodeTwin AI adds three things on top of test selection:

| | What you get |
|---|---|
| **Stated risk** | an estimate of the residual risk `r(c)` of each selection: the chance that it misses an affected test |
| **A target you choose** | a miss-rate target `α` (e.g. 10%); the selection threshold is calibrated against it and keeps adapting as the project changes |
| **Honest abstention** | when `r(c) > α` it abstains to a broader run, and it lists what it could not see (dynamic calls, new or unparsed files) |

## Research results

The method was evaluated on **681 code changes of 8 open-source Python projects**, with three ground truths:
per-test coverage, 812 seeded faults that the tests detect, and the published ground truth of NameRTS.

- A threshold calibrated once on older commits **drifted**: at a 10% target it missed affected tests on 17.5% of later changes.
- With **adaptive conformal calibration**, the observed miss rates were 4.5%, 9.3% and 19.9% for targets of 5%, 10% and 20%,
  while saving 39.1% of test time at the 10% target.
- **Abstaining when the estimated risk exceeds the target** caught 26 of the 31 changes on which line-coverage
  selection missed tests (rule-based triggers caught 7), giving 98.2% safe changes while saving 29.7% of test time.
- Honest limits: the learned ranking was not better than a coverage ranking, and plain file-level coverage was
  already safe on these small libraries; CodeTwin's added value is a stated, adjustable risk.

Paper source, scripts and data: branches [`study-v2`](../../tree/study-v2) (scripts and paper) and
[`study-v2-results`](../../tree/study-v2-results) (data, results, figures).

## Installation

Using CodeTwin in your own project. To work **on** CodeTwin, follow
[Development setup (step by step)](#development-setup-step-by-step) instead.


Requires Python 3.11+ and `git`. The project you analyse can be in Python (pytest), JavaScript/TypeScript, Go, Java,
Kotlin, Rust, C#, Ruby, PHP, C/C++ or any language with a tree-sitter grammar and a test runner that writes coverage;
see [docs/languages.md](docs/languages.md). For languages other than Python install `codetwin[languages]`.

From a release (recommended): download the wheel and the `.vsix` from the
[Releases](../../releases) page, then

```bash
pip install "codetwin-X.Y.Z-py3-none-any.whl[mcp,server,languages]"   # CLI, MCP server, dashboard, all languages
code --install-extension codetwin-X.Y.Z.vsix                  # VS Code extension
```

From source:

```bash
git clone https://github.com/aaryagodbole/CodeTwin.git
cd CodeTwin
pip install -e ".[mcp,server]"     # add ",dev" for development tools
```

## Quick start

Run these inside the project you want to analyse:

```bash
codetwin init          # detects the language and test runner, writes .codetwin.toml; check it
codetwin record        # runs the suite once with per-test coverage on a clean checkout
# ... edit some code ...
codetwin select        # which tests to run, the estimated residual risk, PROCEED or ABSTAIN
```

Example output:

```
decision: PROCEED   estimated residual risk: 3.1%   mode: calibrated
  - estimated residual risk 3.1% <= target 10%
selected 2 test files:
  tests/test_end_to_end.py
  tests/test_risk.py
```

## Commands

| Command | What it does |
|---|---|
| `codetwin init [--language go]` | create `.codetwin.toml` (language, source and test folders, test runner, target α) |
| `codetwin record` | run the full suite with per-test coverage and store it as evidence for the current commit |
| `codetwin select [--alpha 0.05] [--json]` | select tests for the changes since the recorded commit; calibrated mode |
| `codetwin select --budget 0.25` | best tests within 25% of full-suite time, with the risk left behind |
| `codetwin impact FILE...` | tests reached by files, with how each link is known, and unresolved links |
| `codetwin graph FILE [--lines 10-24] [--json]` | impact graph around a file or selected lines (importers, dependencies, tests, unknowns) |
| `codetwin serve` | web dashboard and read-only API on `http://127.0.0.1:8765` |
| `codetwin llm [--test]` | LLM settings for explanations (Groq, Gemini) and a connection test |
| `codetwin learn` | run the full suite, record whether the last selection missed a test, update calibration |
| `codetwin explain` | the numbers and reasons behind the last decision |
| `codetwin run [TEST...]` | run the last selection (or the given test files) with the project's own test runner |
| `codetwin weakcheck` | changed functions that tests execute but do not check (extreme mutation) |

All commands accept `-C PATH` to run on another repository.

## Configuration

`.codetwin.toml` in the project root (Python shown; other languages use `[runner]`, see
[docs/languages.md](docs/languages.md)):

```toml
[project]
language = "python"              # or javascript, go, java, ...; "auto" detects it
src_root = "src"                 # directory added to PYTHONPATH ("." or "src")
packages = ["mypackage"]         # packages measured by coverage
source_dirs = ["src/mypackage"]  # directories with source files
tests_dir = "tests"

[selection]
alpha = 0.10                     # target miss rate
budget = 0.25                    # share of full-suite time in budget mode
aci_gamma = 0.02                 # step size of adaptive calibration
fallback = "file-coverage"       # broader run on abstention: file-coverage | full

[llm]                            # optional: plain-language explanations; keys from GROQ_API_KEY / GEMINI_API_KEY
provider = "groq"                # groq | gemini (both have free tiers)
fallback = "gemini"
```

LLM setup and privacy: [docs/llm.md](docs/llm.md). The LLM only explains; decisions and risk come from the
calibrated engine.

Evidence is stored locally in `.codetwin/` (add it to `.gitignore`). No code leaves your machine.

## How it works

```
Layer 4  Interfaces      CLI · VS Code extension · GitHub Action · MCP server for AI agents
Layer 3  Risk/decision   7 features → risk model → calibrated threshold (CRC + adaptive) → r(c) → proceed / abstain
Layer 2  Store/graph     SQLite evidence store · typed impact graph (static, runtime, co-change, unresolved)
Layer 1  Evidence        git diff (changed lines) · AST facts · per-test coverage and run times
```

1. **Evidence.** `codetwin record` runs the tests with per-test-file coverage (Python: pytest with coverage.py
   dynamic contexts; other languages: each test file on its own with the project's runner), so every test file's
   executed lines are known. The syntax tree (Python `ast`, otherwise tree-sitter) gives dependencies, dynamic
   calls, function spans and lines that run at load time.
2. **Features.** For each test file: did it run a changed line / the changed function / the changed file in the
   recorded version, import distance to the changed module, name match, co-change history, and whether the test
   itself changed. Only evidence from *before* the change's tests run is used.
3. **Selection.** A logistic model scores each test. In calibrated mode the threshold comes from conformal risk
   control on earlier changes; adaptive conformal inference lowers the level after a miss and relaxes it after
   safe changes, so the miss rate tracks the target as the project drifts.
4. **Residual risk and abstention.** `r(c) = 1 − ∏ (1 − p̃ᵢ)` over skipped tests, with isotonic recalibration.
   If `r(c) > α`, CodeTwin abstains and runs the broader file-coverage selection (or the full suite).
5. **Learning.** `codetwin learn` runs the full suite (e.g. nightly or after merge), checks whether the selection
   missed an affected test, and updates the calibration set, recalibration and adaptive level.

Details: [docs/architecture.md](docs/architecture.md).

## Integrations

**VS Code** – `extensions/vscode`: select code (or put the cursor in a function) and run
*CodeTwin: Show impact graph of selection* (right-click, `Ctrl+Alt+I`): a graph opens beside the editor with the
files that import it, its dependencies, the tests that execute the selected lines and the links that cannot be
followed, each edge styled by how it is known. Hovering a function shows `used by N · M tests · K unknown`.
Also: *Select tests for my change*, *Record evidence*, *Explain last decision*; the status bar shows the decision
and risk. Develop with `npm ci && npm run compile`, then press F5.

**Web dashboard** – `dashboard/` (Next.js): overview, system map, decisions, results (observed miss rate vs
target) and the impact graph of any file. `codetwin serve` serves it with the API; see
[dashboard/README.md](dashboard/README.md).

**GitHub Actions** – `action/`: on a pull request, records evidence on the base branch, selects tests for the PR,
writes the decision and risk to the job summary and runs the selected tests:

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- uses: actions/setup-python@v5
  with: { python-version: "3.12" }
- run: pip install -r requirements.txt          # the project's own test dependencies
- uses: aaryagodbole/CodeTwin/action@main
  with:
    alpha: "0.10"
    package: "codetwin"                        # or a wheel URL from a CodeTwin release
```

**AI coding agents (MCP)** – `codetwin-mcp` exposes `verify_change`, `get_impact`, `get_graph`,
`recommend_tests` and `explain_decision`, so an agent can ask before it opens a pull request. Setup: [docs/mcp.md](docs/mcp.md).

## Project structure

```
src/codetwin/
  evidence/          diff, static facts, per-test coverage                     (Layer 1)
  store/             SQLite evidence store + migrations/*.sql                  (Layer 2)
  graph/             typed impact graph                                        (Layer 2)
  risk/              features, model, calibration, residual risk               (Layer 3)
  selection.py       budget/threshold selection, proceed/abstain, output       (Layer 3)
  report/            sections added to every decision (one file each)
  commands/          CLI commands (one file each)
  mcp_tools/         MCP tools for AI agents (one file each)
  server/            read-only HTTP API for the dashboard
  crossrepo/ contracts/ llm/   planned modules (see docs/roadmap.md)
  engine.py, cli.py, mcp_server.py, config.py, plugins.py   shared core
tests/               unit tests and end-to-end tests on throwaway git repositories
extensions/vscode/   VS Code extension; src/features/ has one file per editor feature
dashboard/           web dashboard (Next.js), served by `codetwin serve`
action/              GitHub composite action
docs/                architecture (incl. extension points), output contract, roadmap, MCP setup
scripts/check.sh     lint + tests + extension build (the definition of done)
AGENTS.md            instructions for AI coding agents working on this repository
```

New features never edit the shared core: see
[docs/architecture.md → Extension points](docs/architecture.md#extension-points-how-to-add-a-feature-without-editing-shared-files).

## Development setup (step by step)

Written for someone setting up a project for the first time. Follow the steps in order; each one says what it
does and what you should see. Lines starting with `#` are comments; do not type them.

> **On Windows, type every command in Git Bash** (installed with Git in step 1), not in Command Prompt or
> PowerShell, so the commands below work exactly as written. To get Git Bash inside VS Code:
> **Terminal → New Terminal**, then the **⌄** next to **+** → **Git Bash**. To make it the default:
> `Ctrl+Shift+P` → *Terminal: Select Default Profile* → **Git Bash**.
> On macOS use *Terminal*, on Linux any terminal. CI runs these steps on Windows and Linux for every pull request.

> **No installs at all?** Open the repository on GitHub → **Code → Codespaces → Create codespace on dev**.
> Everything below (steps 1–6) is done for you in a browser VS Code; continue at step 7.

### 1. Install the tools (once per laptop)

| Tool | Version | Download | Check it worked |
|---|---|---|---|
| Git | any recent | https://git-scm.com/downloads (Windows: keep the default options, they include **Git Bash**) | `git --version` |
| Python | **3.11 or newer** (3.12 recommended) | https://www.python.org/downloads/ (Windows: tick **"Add python.exe to PATH"** on the first screen) | `python --version` (macOS/Linux may need `python3 --version`) |
| Node.js | **22 LTS** | https://nodejs.org/ (choose the LTS button) | `node --version` and `npm --version` |
| VS Code | any recent | https://code.visualstudio.com/ | open it once |
| GitHub CLI | any recent | https://cli.github.com/ | `gh --version` |

Close and reopen the terminal after installing, so it finds the new programs. If a check command prints a
version number, that tool is ready.

Windows: if `python --version` opens the Microsoft Store or prints nothing, Windows is using its built-in shortcut
instead of the real Python. Turn it off: **Settings → Apps → Advanced app settings → App execution aliases** →
switch off *python.exe* and *python3.exe*, then reopen Git Bash.

### 2. Get access to the repository

1. Accept the invitation e-mail from GitHub (or open https://github.com/notifications). The repository is
   private, so you cannot see it until you accept.
2. Turn on two-factor authentication: GitHub → your photo → **Settings → Password and authentication**.
3. Log the terminal in to GitHub (choose *GitHub.com*, *HTTPS*, *Login with a web browser*):
   ```bash
   gh auth login
   ```
4. Tell Git who you are (use the e-mail of your GitHub account, so commits show your name):
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

### 3. Download the code

```bash
cd ~                                   # go to your home folder (or any folder you like)
git clone https://github.com/aaryagodbole/CodeTwin.git
cd CodeTwin
git checkout dev                       # all work starts from the dev branch
```

You should now have a `CodeTwin` folder. Open it in VS Code: **File → Open Folder… → CodeTwin**
(VS Code may suggest extensions for Python, Ruff and ESLint; install them).

### 4. Create a Python virtual environment and install the project

A *virtual environment* is a private folder of Python packages for this project only, so it does not clash
with anything else on your laptop.

```bash
python -m venv .venv                   # creates the .venv folder (use python3 if python is not found)
```

Activate it, every time you open a new terminal for this project:

| Your system | Command |
|---|---|
| macOS / Linux | `source .venv/bin/activate` |
| **Windows (Git Bash)** | `source .venv/Scripts/activate` |
| Windows, PowerShell (not recommended) | `.venv\Scripts\Activate.ps1` |

The prompt now starts with `(.venv)`. Then install CodeTwin and the development tools (takes a few minutes):

```bash
python -m pip install --upgrade pip
pip install -e ".[dev,mcp,server]"
```

`-e` means *editable*: your code changes take effect without reinstalling. Check: `codetwin --version`
should print `codetwin 0.1.0` (or newer).

### 5. Install the JavaScript parts (VS Code extension and dashboard)

```bash
cd extensions/vscode && npm ci && cd ../..
cd dashboard && npm ci && cd ..
```

`npm ci` installs exactly the versions in `package-lock.json`. You end up back in the `CodeTwin` folder.

### 6. Run all checks

```bash
bash scripts/check.sh
```

This runs what CI runs on every pull request: lint (ruff), type check (mypy), the tests with coverage,
and the extension and dashboard builds. It takes about a minute and must end with:

```
check: OK
```

If it does, your setup is complete. If not, see *Common problems* below.

### 7. Try CodeTwin on this repository

```bash
codetwin record                        # runs the test suite once with coverage and stores the evidence
echo "# try" >> src/codetwin/selection.py     # make a small change
codetwin select                        # which tests the change needs, the risk, PROCEED or ABSTAIN
codetwin graph src/codetwin/selection.py      # who uses this file, which tests run it, what is unknown
git checkout src/codetwin/selection.py # undo the change
```

**Dashboard:** run `codetwin serve` and open http://127.0.0.1:8765/api/docs (the API). To work on the
dashboard pages, keep `codetwin serve` running and in a second terminal run `cd dashboard && npm run dev`,
then open http://localhost:3000. Stop a running server with **Ctrl+C**.

**VS Code extension:** in VS Code open the folder `extensions/vscode` and press **F5**. A second VS Code
window opens with the extension loaded. In that window open a Python project (for example this repository),
select some code, right-click → **CodeTwin: Show impact graph of selection**.

**Optional, AI explanations:** create a free key at https://console.groq.com/keys, then
`export GROQ_API_KEY=your-key` and `codetwin llm --test` (details in [docs/llm.md](docs/llm.md)).
Never commit a key.

### 8. Make your first change (the team workflow)

Nobody pushes to `dev` or `main` directly. Every change goes through a pull request (PR):

```bash
git checkout dev && git pull           # 1. start from the latest dev
git checkout -b feature/test-gaps      # 2. a new branch for your task (use your task's branch name from Notion)
# 3. edit the code, add a test for it
bash scripts/check.sh                  # 4. must end with "check: OK"
git add -A                             # 5. stage your changes
git commit -m "Add test-gap report"    # 6. save them with a short message saying what changed
git push -u origin feature/test-gaps   # 7. upload the branch to GitHub
```

8. GitHub shows a **Compare & pull request** button: open the PR **into `dev`**, fill in the template
   (what, how you tested it) and add a line to `CHANGELOG.md` under *Unreleased*.
9. Wait for the checks on the PR to turn green and for a review. Fix comments by committing again on the same
   branch and pushing; the PR updates itself.
10. After it is merged: `git checkout dev && git pull`, then start the next task with a new branch.

Before opening a PR, if `dev` has moved on: `git fetch origin && git rebase origin/dev`, run the checks
again, then `git push --force-with-lease`.

Where to put new code (one file per feature, so two people never edit the same file):
[docs/architecture.md → Extension points](docs/architecture.md#extension-points-how-to-add-a-feature-without-editing-shared-files).
Rules for AI coding assistants: [AGENTS.md](AGENTS.md).

### Common problems

| Problem | Fix |
|---|---|
| `python: command not found` | use `python3` (macOS/Linux) or `py` (Windows), or reinstall Python with "Add to PATH" ticked |
| `codetwin: command not found` | the virtual environment is not active: run the `activate` command from step 4 |
| PowerShell: *running scripts is disabled* | run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Git Bash |
| `Permission denied: scripts/check.sh` | run it as `bash scripts/check.sh` |
| `$'\r': command not found` (Windows) | the file has Windows line endings; run `git config --global core.autocrlf input`, then `git rm -r --cached -q . && git reset --hard` (only with no unsaved changes) |
| VS Code terminal shows `PS C:\...>` | that is PowerShell; open a **Git Bash** terminal instead (see the note at the top) |
| `codetwin` works in one terminal but not another (Windows) | every new terminal needs `source .venv/Scripts/activate` first |
| `Repository not found` when cloning or pushing | accept the GitHub invitation and run `gh auth login` again |
| `npm ci` fails | check `node --version` is 22 or newer; delete `node_modules` and run `npm ci` again |
| Tests fail with a *git* error | Git must be installed and `git config --global user.name/user.email` set (step 2) |
| `codetwin select` says *no recorded run* | run `codetwin record` first, on a clean checkout |
| Port 8765 already in use | another `codetwin serve` is running; stop it or use `codetwin serve --port 8770` |

More: CI and release details in [docs/releasing.md](docs/releasing.md), repository settings in
[docs/github-setup.md](docs/github-setup.md), all changes in [CHANGELOG.md](CHANGELOG.md).

## Roadmap

| Status | Work |
|---|---|
| done | Engine, CLI, MCP server; VS Code impact graph of a selection; web dashboard; Action skeleton; CI and releases; research study and paper |
| next | Test gaps, blind spots and evidence cards; symbol-level impact and CodeLens; PR comment; trained per-project models |
| later | PR comment and merge gate; agent-in-the-loop demo; cross-repository evidence; verified LLM link suggestions |

Full plan: [docs/roadmap.md](docs/roadmap.md).

## License

[MIT](LICENSE)
