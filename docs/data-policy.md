# Data policy (CodeTwin Cloud)

This page says what the hosted CodeTwin service (`docs/cloud.md`) stores, why, for how long, and how to remove it.
It applies only when someone uploads reports. The CLI, VS Code extension, MCP server and GitHub Action work
fully offline and send nothing anywhere unless an upload is switched on.

## What a report contains

One report is uploaded per decision (one `codetwin select` / one Action run):

| Field | Example | Why |
|---|---|---|
| Repository | `aaryagodbole/CodeTwin` | which project the report belongs to |
| Commits | head and base SHA, branch, pull-request number | link the report to the change |
| CI run | workflow run id and attempt | deduplicate retries |
| Decision | `proceed` / `abstain`, residual risk, target `alpha`, threshold, mode | the result being shown |
| Tests | test file or test id, selected or not, risk score, duration | why each test was chosen |
| Reasons | e.g. `estimated residual risk 3.1% <= target 10%` | human-readable explanation |
| Report sections | `extras`: e.g. changed files, test gaps (file paths and line numbers), freshness | the evidence summary |
| Outcome (later) | missed: yes/no, failing test ids | measure how often a selection was unsafe |
| Engine version | `codetwin 0.2.0`, output schema version | compatibility |

## What is never uploaded

- source code, diffs or patches, test code
- coverage line maps (which lines each test ran), the git history, the evidence database
- environment variables, secrets, API keys, tokens (the OIDC token is verified and then discarded)
- commit messages and author names or emails

`codetwin push --dry-run` prints the exact JSON that would be sent, without sending it.

## Who can see it

- **Public projects** (marked public by their owner, e.g. CodeTwin itself and the examples): anyone with the link.
- **Private projects:** only signed-in members (GitHub login) of the repository's owner on the service.
- Uploads are accepted only from GitHub Actions jobs of the repository named in the OIDC token, or with a
  project token on a self-hosted server.

## Retention and deletion

- Reports are kept for **90 days**, then deleted automatically.
- A project owner can delete one report or the whole project at any time. Deletion removes the rows; backups
  roll over within 7 days.
- Turning the upload off stops new reports. Existing ones expire on their own, or the owner deletes them.

## Where it is stored

Postgres on Neon, behind the API on Vercel. Data is encrypted in transit (TLS) and at rest (provider default).
Self-hosted installations (Docker Compose) keep everything on the operator's own servers.

## Contact

Questions or deletion requests: open an issue in `aaryagodbole/CodeTwin`, or follow SECURITY.md for anything
sensitive.
