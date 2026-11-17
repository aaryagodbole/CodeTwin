# CodeTwin AI dashboard

Web dashboard for the team and reviewers: overview, system map, decisions, results (calibration) and the impact
graph of any file. Next.js (App Router, static export) + Tailwind CSS + TanStack Query + Cytoscape.js + Recharts.
It only reads the CodeTwin API (`src/codetwin/server/`), which reads the same SQLite evidence store as the CLI.

```bash
# terminal 1, in a project with .codetwin.toml
pip install "codetwin[server]"
codetwin serve                      # API on http://127.0.0.1:8765 (docs at /api/docs)

# terminal 2
cd dashboard
npm install
npm run dev                         # http://localhost:3000, talks to the API (see .env.development)
```

Production: `npm run build` writes `out/`; then `codetwin serve --static dashboard/out` serves the dashboard and
the API from one process.

## API routes

| Route | Description |
|---|---|
| `GET /api/health` | Service health status and version |
| `GET /api/summary` | Project configuration, recorded commit, and evidence counts |
| `GET /api/decisions` | Recent decisions list (newest first) |
| `GET /api/decisions/{id}` | Single decision details with selection reasons, outcome, and per-test risk scores |
| `GET /api/flaky` | Flaky tests (passed and failed on same commit), grouped by test and sorted by failures |
| `GET /api/kg` | Code knowledge graph (`nodes`, `edges`, `stats`); `?symbols=false` omits symbol nodes |
| `GET /api/calibration` | Observed miss rate over time against target alpha |
| `GET /api/map` | Whole-project file and test dependency map |
| `GET /api/graph` | Impact graph for a file and line range (`?file=...&lines=...`) |
| `GET /api/llm` | LLM explanation provider availability |

Structure: `src/app/<page>/page.tsx` per page, `src/components/` shared UI, `src/lib/api.ts` typed API client.
Add a page as a new folder in `src/app/` and a link in `src/components/nav.tsx`.
