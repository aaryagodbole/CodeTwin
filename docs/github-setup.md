# GitHub setup (GitHub Pro, private repository)

Everything that can live in the repository is already here; this page lists the clicks in **Settings** that
the repository owner does once. Rulesets on a private repository need GitHub Pro (included in the GitHub
Student Developer Pack).

## 1. Rulesets (branch and tag protection)

**Settings → Rules → Rulesets → New ruleset ▾ → Import a ruleset**, once for each file:

| File | Protects | Rules |
|---|---|---|
| `.github/rulesets/main.json` | `main` | pull request (from `dev`) with 1 approval and code-owner review, conversations resolved, **merge commit only**, all CI checks green and up to date, no force push, no deletion |
| `.github/rulesets/dev.json` | `dev` | same, but **squash merge only** and linear history (one commit per feature) |
| `.github/rulesets/release-tags.json` | `v*` tags | a published release tag cannot be moved or deleted |

Required checks: `lint`, `typecheck`, `security`, `test (3.11)`, `test (3.12)`, `test (3.13)`, `package`,
`vscode-extension`, `dashboard`, `action`, `windows`. Repository admins can merge a pull request without the approval
(bypass mode *pull request*), but nobody can push directly to `main` or `dev`.

## 2. General settings

**Settings → General → Pull Requests**
- Allow **squash merging** (feature → `dev`) and **merge commits** (`dev` → `main`); untick rebase merging.
  The rulesets decide which method each branch accepts. Squashing `dev` into `main` would make the two
  branches diverge, so `main` only accepts merge commits.
- Tick **Always suggest updating pull request branches**, **Allow auto-merge**,
  **Automatically delete head branches**.

**Settings → General → Features:** untick Wikis (documentation lives in `docs/`).

**Settings → Actions → General → Workflow permissions:** *Read repository contents and packages permissions*.
Workflows that need more ask for it (`release.yml` asks for `contents: write`).

## 3. Environments (release secrets)

**Settings → Environments → New environment**
- `release`: *Deployment branches and tags* → **Selected** → add `main` and tag pattern `v*`.
  Add secrets `VSCE_PAT` (VS Code Marketplace) and `OVSX_PAT` (Open VSX) here when the stores are set up.
- `pypi`: same branch/tag rule; used by PyPI trusted publishing (no secret needed). See [releasing.md](releasing.md).

## 4. Security

**Settings → Code security**
- Enable **Dependabot alerts** and **Dependabot security updates** (version updates are configured in
  `.github/dependabot.yml`: one grouped pull request per ecosystem per month).
- Enable **Private vulnerability reporting** (used by `SECURITY.md`).

## 5. Codespaces

`.devcontainer/` sets up Python 3.12, Node 22, all dependencies and the pre-commit hook. **Code → Codespaces →
Create codespace on dev**, then run `scripts/check.sh`. Ports 8765 (API + dashboard) and 3000 (dashboard dev
server) are forwarded.

## Not included in GitHub Pro for private repositories

| Feature | Needs | What this repository does instead |
|---|---|---|
| Code scanning (CodeQL), secret scanning push protection | GitHub Advanced Security (organization plan) | ruff security rules (`S`) and mypy in CI, `pip-audit` and `npm audit` in the `security` job, Dependabot alerts |
| Merge queue | organization repository | required checks must be up to date with the base branch (strict mode) |
| Required reviewers or wait timers on environments | GitHub Enterprise for private repositories | deployments limited to `main` and `v*` tags |
