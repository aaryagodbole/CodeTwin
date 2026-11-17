# 0003. A cloud plane that receives decision reports, never code

Status: Accepted (November 2026)

## Context

CodeTwin runs where the code is: on a developer's laptop (CLI, VS Code, MCP) and in CI (the GitHub Action). Its
evidence store is a local SQLite file. That is right for the method: the paper's analysis needs the code, the
coverage and the git history, and none of it should leave the machine.

A team also needs a shared view: which pull requests CodeTwin judged, how much test time it saved, whether its
selections missed tests, across projects and people. Today that view exists only on the machine that ran
`codetwin serve`. The project also needs a public URL for reviewers and the final demo.

Comparable tools split the work the same way. Launchable sends change and test *metadata* from CI to its
service and states that source code is never sent. Datadog Test Impact Analysis sends per-test coverage to its
backend. Develocity runs predictive test selection inside the customer's own infrastructure. Codecov accepts
uploads from GitHub Actions authenticated with GitHub OIDC instead of a stored token.

Options:

1. Run the engine as a service, so CI sends code or diffs to it. Rejected: code leaves the customer's
   infrastructure, and the paper's method would depend on a server.
2. Share the SQLite file (commit it, or put it in object storage). Rejected: binary merges, no access
   control, and it holds coverage line maps that a dashboard does not need.
3. A separate **cloud plane** that receives each decision as a small JSON **report**, stores it in Postgres
   and serves the dashboard. The engine stays local and unchanged.

## Decision

Option 3.

- **Boundary.** A report holds repository and commit identifiers, the decision, test identifiers with their
  risk scores, report sections (`extras`), and later the outcome. It holds no source code, diffs, test code,
  coverage line maps or secrets. `docs/data-policy.md` lists every field.
- **Upload authentication.** GitHub Actions uploads with a GitHub OIDC token: short-lived, issued per job,
  bound to the repository. There are no long-lived upload tokens. Local uploads (`codetwin push`) are for
  self-hosted servers only.
- **Same API contract.** The cloud API serves the same read endpoints as `codetwin serve`, so the dashboard
  works against either. It adds `POST /api/v1/reports` for uploads.
- **Hosting.** The dashboard and the API run on Vercel as two projects from this repository: the Next.js
  dashboard (`dashboard/`) and the API (`cloud/`, FastAPI as one Vercel Function). The API is a separate small
  package, because it does not need the analysis engine and its heavy parser dependencies. The database is Neon Postgres, with a database branch per preview deployment. A Docker Compose file
  runs the same API, dashboard and Postgres on one's own servers (self-hosting).
- **Opt-in.** Nothing is uploaded unless the user runs `codetwin push` or enables the Action's upload input.
  Without it, CodeTwin works fully offline, as described in the paper.

## Consequences

- The method and the paper are unaffected: the cloud plane only displays reports the engine already produced.
- We now operate a service that holds data, so we need a data policy, retention, deletion and access control
  (`docs/data-policy.md`, `docs/cloud.md`).
- Serverless functions keep no files, so the cloud API stores everything in Postgres; it cannot reuse the
  SQLite store. The read endpoints are implemented twice (SQLite locally, Postgres in the cloud) behind one
  contract. A contract test keeps them in step.
- Free tiers bound the scale: Neon Free has 1 GB of storage and 10 branches per project. Reports are a few
  kilobytes each, so storage is not the limit. Preview branches must be deleted when a pull request closes.
- Until the cloud API is live, the hosted dashboard shows a demo snapshot (`docs/dashboard.md`).
