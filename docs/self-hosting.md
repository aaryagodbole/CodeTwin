# Self-hosting CodeTwin Cloud

Run the whole cloud plane (Postgres, the API from `cloud/`, the dashboard) on your own machine or servers with
Docker Compose, so no report ever leaves your network. The hosted version on Vercel runs the same API code
(`docs/cloud.md`).

## Start it

```bash
docker compose up -d --build --wait          # from the repository root; first build takes a few minutes
docker compose exec api python -m codetwin_cloud add-project OWNER/NAME --public --token
```

The second command registers a repository and prints an **upload token** once. Store it as a CI secret.

| URL | What |
|---|---|
| http://localhost:3000 | dashboard (demo data for now; it reads the API once cloud mode lands) |
| http://localhost:8080/api/docs | API, with an interactive documentation page |
| http://localhost:8080/api/health | health check (`"database": "ok"`) |

Ports are bound to `127.0.0.1` only. To expose the stack, put a reverse proxy with TLS in front of it.
`codetwin push` refuses plain `http` for anything other than localhost.

## Upload from a project

```bash
codetwin select --json > decision.json
codetwin push --decision decision.json --server http://localhost:8080 --token ctp_...      # add --dry-run to preview
```

From CI with no OIDC trust to your server, set `CODETWIN_SERVER` and `CODETWIN_TOKEN` (as a secret) and run the
same command with `--best-effort`.

## Configuration (`.env` next to `compose.yaml`)

| Variable | Default | Set it when |
|---|---|---|
| `POSTGRES_PASSWORD` | `codetwin-local-only` | always, before anything other than local use |
| `CRON_SECRET` | empty (retention job disabled) | you want reports older than 90 days deleted |
| `CODETWIN_CORS_ORIGINS` | `http://localhost:3000` | the dashboard is served from another address |

Retention: without Vercel Cron, call the job daily from the host's scheduler, e.g.
`curl -H "Authorization: Bearer $CRON_SECRET" http://localhost:8080/api/cron/retention`.

## Operate it

- Logs: `docker compose logs -f api`. One JSON line per request, never bodies or tokens.
- Backups: `docker compose exec db pg_dump -U codetwin codetwin > backup.sql`.
- Upgrade: `git pull && docker compose up -d --build`. Migrations run when the API first uses the database.
- Stop and delete everything, including the data: `docker compose down -v`.

CI checks this setup on every pull request (job `self-host`). It builds the images, starts the stack, uploads a
real decision with `codetwin push`, and reads it back.
