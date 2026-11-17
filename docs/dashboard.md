# Dashboard: see it locally, deploy it, check pull requests

The dashboard (`dashboard/`, Next.js static export) only reads the CodeTwin API. It can get its data in two ways:

| Mode | Data comes from | Used for |
|---|---|---|
| **live** (default) | a running `codetwin serve` on your project | your own work, on your laptop |
| **demo** | `dashboard/public/demo/`: JSON answers of the API, written by `scripts/demo_snapshot.py` from a real engine run on `examples/python` | the hosted dashboard (Vercel), and quick previews without setting up a project |

Demo mode shows a grey banner saying so, so a snapshot is never mistaken for a live project.

## See it on localhost

Prerequisites: Node 22 and the Python setup from the README (`pip install -e ".[dev,mcp,server]"`).

### 1. Quickest: demo data (no project needed)

```bash
cd dashboard
npm ci
npm run dev:demo            # open http://localhost:3000
```

### 2. Your own project (live)

```bash
# terminal 1: in any project with .codetwin.toml (e.g. a copy of examples/python after init + record)
codetwin serve              # API on http://127.0.0.1:8765, docs at http://127.0.0.1:8765/api/docs

# terminal 2
cd dashboard
npm run dev                 # http://localhost:3000, reads the API above (dashboard/.env.development)
```

Make a change in the project and run `codetwin select`; refresh the dashboard to see the new decision.

### 3. Exactly what Vercel deploys

```bash
python scripts/demo_snapshot.py          # optional: regenerate the demo data with your branch's engine
cd dashboard
npm run build:demo                       # static site in dashboard/out
npx serve out                            # or: python -m http.server 4173 -d out
```

Use this to check your branch before pushing. If `scripts/demo_snapshot.py` fails, or the build fails, the
deployment would fail too. CI runs the same steps (job `dashboard-demo`).

### See your own feature

- **New API endpoint** (e.g. `/api/flaky`): run your branch's `codetwin serve` and open
  `http://127.0.0.1:8765/api/docs` to try it. Add the request to `capture()` in `scripts/demo_snapshot.py` when a
  dashboard page starts using it.
- **New report section** (e.g. `freshness`): `codetwin select --json` shows it under `extras`. The dashboard's
  decision page (in progress) will list every section automatically.
- **VS Code feature**: press F5 in `extensions/vscode` (README → VS Code).

## Deploy (Vercel)

The hosted dashboard is the demo build, configured in `dashboard/vercel.json`. To set it up (one time, by the
repository owner):

1. Sign in at [vercel.com](https://vercel.com) with GitHub. Choose **Add New → Project** and import
   `aaryagodbole/CodeTwin`.
2. Set **Root Directory** to `dashboard`. Framework, build and output settings come from `vercel.json`; leave
   them as detected.
3. Under **Settings → Git**, set the **Production Branch** to `main`. Every other branch, including `dev` and
   every pull request, gets a **preview deployment** with its own URL.
4. Deploy. Production updates when `main` changes; `dev` and pull requests get previews.

## Pull-request checks

Every pull request gets two deployment checks:

| Check | What it proves |
|---|---|
| **CI → dashboard-demo** | The current engine still produces the snapshot, and the demo build contains every API answer |
| **Vercel** (status from the Vercel GitHub app) | The real deployment builds, plus a preview link to click |

To make them required, add both to the `dev` ruleset (Settings → Rules → Rulesets → *dev* → Require status
checks: `dashboard-demo` and `Vercel`). A pull request that breaks the deployment then cannot be merged.

## Regenerating the demo data

```bash
python scripts/demo_snapshot.py     # about 10 seconds; rewrites dashboard/public/demo/
```

The script copies `examples/python` into a temporary git repository, then runs `init` and `record`. For each
of its edits it runs `select` and `learn`, then reverts the edit. Finally it saves each API answer the dashboard
uses. It refuses to write a file that contains a local path. Commit the regenerated folder when an API answer's
shape changes, or when a page starts using a new endpoint.

The demo is a stopgap. The next step (docs/cloud.md, in progress) replaces it with the cloud API, which receives
real decision reports from CI.
