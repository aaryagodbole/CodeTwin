# CodeTwin Cloud API

Receives decision reports from CI (never code) and serves them to the dashboard. Design and policy:
[docs/cloud.md](../docs/cloud.md), [docs/adr/0003-cloud-plane.md](../docs/adr/0003-cloud-plane.md),
[docs/data-policy.md](../docs/data-policy.md).

This is a separate small package. It needs only FastAPI, psycopg and PyJWT, not the analysis engine, so it
deploys as its own lightweight Vercel Function.

```
cloud/
  app.py                    Vercel entry point (`app`)
  vercel.json               daily retention cron, headers
  codetwin_cloud/
    app.py                  routes: health, upload, read (same shapes as `codetwin serve`), retention
    auth.py                 GitHub OIDC verification, project tokens
    models.py               the report format codetwin.report/v1 (strict: unknown fields are refused)
    db.py                   connections and migrations
    migrations/NNNN_*.sql   schema (never edit an applied file; add the next number)
    __main__.py             operator commands: migrate, add-project, new-token
  tests/                    run against a real Postgres
```

## Run locally

You need a Postgres database. Use any one of these:

- Docker: `docker run --rm -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:16`
  gives `postgresql://postgres:pw@localhost:5432/postgres`
- A free Neon branch: copy its connection string
- A local install of PostgreSQL 16

```bash
cd cloud
pip install -e ".[dev]"
export DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres
python -m codetwin_cloud add-project acme/shop --public --token   # prints an upload token once
uvicorn app:app --reload --port 8080                               # http://localhost:8080/api/docs
```

Upload a report from a project on your laptop with the token. `codetwin push --server http://localhost:8080`
arrives in the next PR of the stack. Until then, use the request examples in `tests/conftest.py`.

## Tests

```bash
export CODETWIN_TEST_DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres   # wiped by the tests!
python -m pytest
```

Without `CODETWIN_TEST_DATABASE_URL` the database tests are skipped. CI runs them against a Postgres service
container (job `cloud`). One test compares the response shapes with the local API's answers in the dashboard
demo snapshot (the contract test).

## Deploy (Vercel + Neon)

A second Vercel project, next to the dashboard. One time, by the repository owner:

1. In Vercel, choose **Add New → Project**, import `aaryagodbole/CodeTwin` again, set **Root Directory** to
   `cloud`, and name it e.g. `codetwin-api`. Vercel detects FastAPI from `app.py`.
2. In **Storage**, add **Neon** (Marketplace) and connect it to this project. That sets `DATABASE_URL`. Enable
   *Create a branch for each preview deployment*, and enable deleting a branch when its Git branch is deleted.
3. Under **Environment Variables**, add:
   - `CRON_SECRET`: a long random string. Vercel Cron sends it to the retention job.
   - `CODETWIN_CORS_ORIGINS`: the dashboard URL, e.g. `https://codetwin.vercel.app`.
4. Deploy, then open `https://<api>.vercel.app/api/health`. It should say `"database": "ok"` (migrations run on
   first use).
5. Register the repositories that may upload. Run this on your laptop with the production `DATABASE_URL` from
   Neon:

   ```bash
   python -m codetwin_cloud add-project aaryagodbole/CodeTwin --public
   ```

GitHub Actions uploads need no secret: the job asks GitHub for an OIDC token (`permissions: id-token: write`).
