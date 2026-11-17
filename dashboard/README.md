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

Demo data without a project: `npm run dev:demo`. How to see it locally, deploy it on Vercel and check pull
requests: [docs/dashboard.md](../docs/dashboard.md).

Production: `npm run build` writes `out/`; then `codetwin serve --static dashboard/out` serves the dashboard and
the API from one process.

Structure: `src/app/<page>/page.tsx` per page, `src/components/` shared UI, `src/lib/api.ts` typed API client.
Add a page as a new folder in `src/app/` and a link in `src/components/nav.tsx`.
