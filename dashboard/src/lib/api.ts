// Typed client for the read-only CodeTwin API (src/codetwin/server/app.py).
// In production the dashboard is served by the API itself, so the base URL is empty (same origin).
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function get<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const qs = params
    ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString()
    : "";
  const res = await fetch(`${BASE}/api${path}${qs}`);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  }
  return (await res.json()) as T;
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
