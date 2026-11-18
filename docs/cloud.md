# CodeTwin Cloud: architecture and operations

Decision record: [adr/0003-cloud-plane.md](adr/0003-cloud-plane.md). What is stored: [data-policy.md](data-policy.md).
Status: being built in the stacked pull requests listed under *Delivery* below. The cloud API lives in `cloud/`
(a separate package: it does not need the analysis engine, so its function stays small).

## Two planes

```
 where the code lives (unchanged)                    CodeTwin Cloud (reports only)
 ──────────────────────────────────                  ──────────────────────────────────────────────
 laptop: CLI · VS Code · MCP ──┐                      Vercel (two projects, one repository)
                               │  codetwin push        ├─ dashboard/  Next.js (static)
 CI: GitHub Action ────────────┼────────────────────▶  ├─ cloud/      FastAPI, one Vercel Function
   engine + SQLite evidence    │  report JSON          │    POST /api/v1/reports   (GitHub OIDC)
   (never uploaded)            │  + OIDC token         │    GET  /api/v1/...       (read, same contract)
                               │                       └─ Neon Postgres  (branch per preview deployment)
                               │
 self-hosted alternative: docker compose (API + dashboard + Postgres) on your own servers
```

The engine decides. The cloud only stores and shows what the engine decided, so nothing in the paper's method
depends on the cloud.

## Report format (`codetwin.report/v1`)

One report per decision. Built by `codetwin push` from the stored decision (id, scores, alpha, threshold) and the
`select --json` output (reasons, report sections).

```json
{
  "schema": "codetwin.report/v1",
  "engine": {"version": "0.2.0", "output_schema": 1},
  "repository": "aaryagodbole/CodeTwin",
  "commit": {"head": "3f9c…", "base": "79dd…", "ref": "refs/pull/63/merge", "pull_request": 63},
  "run": {"source": "github-actions", "id": "12345678", "attempt": 1},
  "decision": {
    "decision": "proceed", "residual_risk": 0.031, "alpha": 0.1, "threshold": 0.42, "mode": "calibrated",
    "selected": ["tests/test_cart.py"],
    "tests": [{"id": "tests/test_cart.py", "selected": true, "score": 0.71, "seconds": 0.4}],
    "reasons": ["estimated residual risk 3.1% <= target 10%"],
    "sections": {"changed_files": {"summary": "2 files changed", "files": ["src/shop/calc.py"]}}
  },
  "outcome": null
}
```

Rules:

- **Sections opt in.** A report section is uploaded only if its module sets `PUBLISH = True`
  (`src/codetwin/report/<name>.py`). The default is not to upload. A section may publish file paths, symbol
  names, line numbers, counts and its summary; never source text. Reviewers check this on the PR that sets
  `PUBLISH = True`.
- Maximum size 256 KB per report. Larger reports are rejected with `413`.
- `schema` is versioned. The server accepts `v1` and rejects anything else with `422`.
- Uploads are idempotent on (repository, run id, run attempt, head SHA): a retried job does not duplicate.

## API

Read endpoints keep the shape of the local API (`src/codetwin/server/app.py`), scoped to a project:

| Method and path | Auth | Purpose |
|---|---|---|
| `GET /api/health` | none | liveness and database check |
| `POST /api/v1/reports` | GitHub OIDC token, or a project token when self-hosted | upload one report → `201 {id}`, or `200` if it already exists |
| `GET /api/v1/projects` | session (public projects without one) | projects the caller can see |
| `GET /api/v1/projects/{owner}/{repo}/summary` | same | as `/api/summary` |
| `GET /api/v1/projects/{owner}/{repo}/decisions?limit=` | same | as `/api/decisions` |
| `GET /api/v1/projects/{owner}/{repo}/decisions/{id}` | same | as `/api/decisions/{id}`, plus the report sections |
| `GET /api/v1/projects/{owner}/{repo}/calibration` | same | as `/api/calibration` |
| `GET /api/v1/projects/{owner}/{repo}/savings` | same | as `/api/savings` (after the local endpoint, #55, is merged) |

The system map and the per-file impact graph need the code's static facts, so they stay **local-only** views
(`codetwin serve`). The hosted dashboard hides them and links to `docs/dashboard.md`.

A contract test runs the same requests against the local API (SQLite) and the cloud API (Postgres, in CI), and
compares the response shapes.

## Upload authentication (GitHub OIDC)

1. The workflow job has `permissions: id-token: write`. The Action requests a token with audience
   `codetwin-cloud` and sends it as `Authorization: Bearer <jwt>`.
2. The API verifies it:
   - signature against GitHub's JWKS (`https://token.actions.githubusercontent.com/.well-known/jwks`, cached)
   - `iss = https://token.actions.githubusercontent.com`
   - `aud = codetwin-cloud`
   - `exp` and `nbf`, with 60 s of leeway
3. `repository` in the token must equal `repository` in the report. `run_id`, `run_attempt` and `sha` in the
   token must equal the report's run id, attempt and head commit, so a job can only upload its own result (one
   token cannot store extra reports by changing the attempt).
4. The repository must be registered (`project` row) and allowed to upload. Unknown repositories get `403`;
   nothing is created implicitly.
5. The token must carry `repository_id`. The first OIDC upload binds the project to that id
   (`project.github_repository_id`); later uploads with another id get `403`. A repository that is renamed,
   transferred, or deleted and recreated under the same name cannot upload into the old project's history. To
   move a project to a new repository on purpose, the operator clears `github_repository_id`.
6. The token is not stored or logged.

Self-hosted servers can also accept a per-project token (stored hashed, shown once), for CI systems without OIDC.

## Database (Postgres)

```
project  (id, owner, name, public, uploads_enabled, created_at)        unique (owner, name)
report   (id, project_id → project, received_at, head_sha, base_sha, ref, pull_request,
          run_source, run_id, run_attempt, engine_version,
          decision, residual_risk, alpha, threshold, mode, selected_count,
          payload jsonb)                                                unique (project_id, run_id, run_attempt, head_sha)
outcome  (report_id → report primary key, missed, failing jsonb, received_at)
```

- Columns for what the dashboard filters and aggregates; the full report in `payload`.
- Index on `report (project_id, received_at desc)`.
- Versioned SQL migrations in `cloud/codetwin_cloud/migrations/`, the same pattern as the local store. They are
  applied on deploy, and each preview deployment applies them to its own Neon branch.
- Retention: a daily Vercel Cron job deletes reports older than 90 days (`docs/data-policy.md`).

## Environments

| Environment | Dashboard and API | Database | Data |
|---|---|---|---|
| Local | `npm run dev` + `codetwin serve` | the project's SQLite | your project |
| Local (cloud stack) | `docker compose up` | Postgres container | uploads from `codetwin push --server http://localhost:8080` |
| Preview (every PR) | Vercel preview URL | Neon branch `preview/<git-branch>`, deleted with the branch | demo / seeded |
| Production (`main`) | Vercel production URL | Neon main branch | CodeTwin's own PRs, examples |

`dev` is deployed as a preview of the `dev` branch and serves as staging.

## Operations

- **Health:** `GET /api/health` checks the database connection; the Vercel deployment check calls it.
- **Logs:** one JSON line per request (request id, route, status, duration, project). No payloads, no tokens.
- **Errors:** Sentry, when `SENTRY_DSN` is set; off by default.
- **Limits:** at most 120 uploads per project per hour (`429` after that; a retry of a report that is already
  stored still gets `200` with its id), 256 KB per report, no NaN or Infinity in numbers (`422`), read endpoints
  paginated (`limit` ≤ 1000).
- **Durability:** an upload is committed before the response is sent, so `201`/`200` means the report is stored.
- **Service levels** (best effort on free tiers): upload p95 < 1 s; dashboard read p95 < 500 ms; a failed
  upload never fails the user's CI job. The Action reports a warning, because CodeTwin's decision does not
  depend on the cloud.
- **Secrets:** only `DATABASE_URL` (injected by the Neon integration) and optional `SENTRY_DSN`, both set in
  Vercel environment variables. No secrets in the repository or in GitHub for uploads.

## Delivery (stacked pull requests)

1. Deployable dashboard with demo data, Vercel config, deployment check on PRs (`docs/dashboard.md`).
2. This design: ADR 0003, this document, the data policy.
3. Cloud API (`cloud/`, its own package and Vercel project): Postgres schema and migrations, OIDC
   verification, upload and read endpoints, retention cron, operator commands, and tests (including the contract
   test). How to run and deploy it: `cloud/README.md`.
4. `codetwin push [--dry-run]`, `PUBLISH` opt-in for report sections, and an `upload` input in the Action.
5. Self-hosting: Dockerfile and `docker-compose.yml`.

After 5: the dashboard reads the cloud API (`NEXT_PUBLIC_DATA_MODE=cloud`), adds a project switcher and GitHub
login, and CodeTwin uploads its own pull requests.
