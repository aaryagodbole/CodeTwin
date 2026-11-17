// Typed client for the read-only CodeTwin API (src/codetwin/server/app.py).
// Two data sources, chosen at build time with NEXT_PUBLIC_DATA_MODE (docs/dashboard.md):
//   "live" (default): a running `codetwin serve`. When the API serves the dashboard itself the base URL is empty.
//   "demo": static JSON in public/demo/, written by scripts/demo_snapshot.py from a real engine run. Used by the
//           hosted dashboard (Vercel), which has no API behind it.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
export const DATA_MODE: "live" | "demo" = process.env.NEXT_PUBLIC_DATA_MODE === "demo" ? "demo" : "live";

/** Snapshot file for a request. Must match `snapshot_name()` in scripts/demo_snapshot.py
 *  (tests/test_demo_snapshot.py): "/summary" -> summary.json; "/decisions" {limit:"10"} -> decisions__limit-10.json;
 *  "/graph" {file:"src/shop/calc.py", lines:"3-4"} -> graph__file-src_shop_calc.py__lines-3-4.json */
export function demoPath(path: string, params: Record<string, string> = {}): string {
  let name = path.replace(/^\/+|\/+$/g, "").replaceAll("/", "_");
  for (const k of Object.keys(params).sort()) {
    name += `__${k}-${params[k]}`;
  }
  return `/demo/api/${name.replace(/[^A-Za-z0-9._-]/g, "_")}.json`;
}

export async function get<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const clean = Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v)) as Record<string, string>;
  const url = DATA_MODE === "demo"
    ? demoPath(path, clean)
    : `${BASE}/api${path}${Object.keys(clean).length ? "?" + new URLSearchParams(clean).toString() : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    if (DATA_MODE === "demo" && res.status === 404) {
      throw new Error("Not in the demo data. Run the dashboard against `codetwin serve` to see this view.");
    }
    throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export interface DemoMeta {
  generated: string;
  project: string;
  edits: number;
  files: string[];
}

export interface Summary {
  root: string;
  packages: string[];
  alpha: number;
  alpha_t: number;
  calibration_size: number;
  recorded_commit: string | null;
  test_files: number;
  suite_seconds: number | null;
  decisions: number;
  labelled_decisions: number;
}

export interface DecisionRow {
  id: number;
  recorded: number;
  base: string;
  mode: string;
  alpha: number | null;
  alpha_t: number | null;
  threshold: number | null;
  residual_risk: number;
  decision: "proceed" | "abstain";
  selected: string[];
  reasons: string[];
  missed: boolean | null;
}

export interface Calibration {
  points: { n: number; decision_id: number; alpha: number; alpha_t: number; observed_miss_rate: number }[];
  labelled: number;
  misses: number;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "target" | "source" | "test" | "unknown";
  path: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  detail?: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  unknowns?: string[];
  summary?: string;
  recorded_commit?: string | null;
}
