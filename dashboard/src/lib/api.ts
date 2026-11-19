// Typed client for the read-only CodeTwin API (src/codetwin/server/app.py).
// Three data sources, chosen at build time with NEXT_PUBLIC_DATA_MODE (docs/dashboard.md):
//   "live" (default): a running `codetwin serve`. When the API serves the dashboard itself the base URL is empty.
//   "cloud": the hosted dashboard. Decisions, summary and calibration come from CodeTwin Cloud
//            (NEXT_PUBLIC_API_URL, project NEXT_PUBLIC_PROJECT = owner/name): real reports uploaded by CI. The cloud
//            holds no code-level data (ADR 0003), so the dependency graph and impact views come from a snapshot of
//            the project's repository in public/snapshot/ (scripts/repo_snapshot.py).
//   "demo": static JSON in public/demo/, written by scripts/demo_snapshot.py from a real run on examples/python.
import { demoPath, snapshotPath } from "./demo-path.mjs";

export { demoPath, snapshotPath };

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
export const PROJECT = process.env.NEXT_PUBLIC_PROJECT ?? "";
const MODE = process.env.NEXT_PUBLIC_DATA_MODE;
export const DATA_MODE: "live" | "demo" | "cloud" = MODE === "demo" ? "demo" : MODE === "cloud" ? "cloud" : "live";

// Endpoints the cloud serves for a project; everything else is read from the repository snapshot.
const CLOUD_PATHS = /^\/(summary|calibration|decisions(\/\d+)?)$/;

/** Where a request goes in the current data mode. */
export function urlFor(path: string, params: Record<string, string> = {}): string {
  const query = Object.keys(params).length ? "?" + new URLSearchParams(params).toString() : "";
  if (DATA_MODE === "demo") return demoPath(path, params);
  if (DATA_MODE === "cloud") {
    return CLOUD_PATHS.test(path)
      ? `${BASE}/api/v1/projects/${PROJECT.split("/").map(encodeURIComponent).join("/")}${path}${query}`
      : snapshotPath(path, params);
  }
  return `${BASE}/api${path}${query}`;
}

export async function get<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const clean = Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v)) as Record<string, string>;
  const res = await fetch(urlFor(path, clean));
  if (!res.ok) {
    if (DATA_MODE === "demo" && res.status === 404) {
      throw new Error("Not in the demo data. Run the dashboard against `codetwin serve` to see this view.");
    }
    if (DATA_MODE === "cloud" && res.status === 404 && !CLOUD_PATHS.test(path)) {
      throw new Error("Not in the repository snapshot (a file added after it was taken). Run `codetwin serve` locally to see it.");
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
  alpha: number | null;     // null on the cloud API before any report carries a target
  alpha_t: number | null;
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
  residual_risk: number | null;
  decision: "proceed" | "abstain";
  selected: string[];
  reasons: string[];
  missed: boolean | null;
}

export interface DecisionDetail extends DecisionRow {
  scores: Record<string, number | null>;
}

export interface FlakyTest {
  test: string;
  passes: number;
  failures: number;
  commits: number;
  last_sha: string;
}

export type KgNodeKind = "repository" | "file" | "test" | "symbol" | "unknown";
export type KgEdgeKind = "contains" | "defines" | "imports" | "covers" | "co_changes" | "unresolved";

export interface KgNode {
  id: string;
  kind: KgNodeKind;
  key?: string;
  name?: string;
  file?: string;
  start?: number;
  end?: number;
  symbol_kind?: string;
  detail?: string;
  [key: string]: unknown;
}

export interface KgEdge {
  source: string;
  target: string;
  kind: KgEdgeKind;
  lines?: number | string;
  commits?: number;
  [key: string]: unknown;
}

export interface KnowledgeGraph {
  nodes: KgNode[];
  edges: KgEdge[];
  stats: {
    nodes: number;
    edges: number;
    node_kinds: Record<string, number>;
    edge_kinds: Record<string, number>;
  };
}

export interface Calibration {
  points: { n: number; decision_id: number; alpha: number; alpha_t: number; observed_miss_rate: number }[];
  labelled: number;
  misses: number;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "target" | "source" | "test" | "unknown" | "module";
  path: string;
  /** module nodes (a folder in the folder view): how many files it holds */
  files?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  detail?: string;
  /** folder view: how many file links this edge stands for */
  weight?: number;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  unknowns?: string[];
  summary?: string;
  recorded_commit?: string | null;
}
