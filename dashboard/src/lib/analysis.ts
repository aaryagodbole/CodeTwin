// Repository-wide analysis, derived in the browser from the read-only `/map` answer.
// Display only: no decision logic lives here (dashboard/AGENTS.md).
import type { DecisionRow, Graph, GraphNode } from "@/lib/api";

export interface FileStat {
  node: GraphNode;
  /** how many other files import it (static edges pointing at it) */
  usedBy: number;
  /** how many test files reach it (static or runtime edge from a test) */
  testedBy: number;
  /** how many files it imports */
  uses: number;
}

export interface RepoAnalysis {
  files: number;
  tests: number;
  unknownNodes: number;
  edges: number;
  edgeTypes: { type: string; count: number }[];
  perFile: FileStat[];
  hubs: FileStat[];
  untested: FileStat[];
  /** share of source files reached by at least one test, 0..1 */
  reach: number;
  /** links the analysis could not resolve, as sentences */
  unresolved: { from: string; to: string }[];
}

export function analyseRepo(g: Graph): RepoAnalysis {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const stat = new Map<string, FileStat>();
  for (const n of g.nodes) {
    if (n.kind === "source" || n.kind === "target") stat.set(n.id, { node: n, usedBy: 0, testedBy: 0, uses: 0 });
  }
  const seenUse = new Set<string>();
  const seenTest = new Set<string>();
  const types = new Map<string, number>();
  const unresolved: { from: string; to: string }[] = [];
  for (const e of g.edges) {
    types.set(e.type, (types.get(e.type) ?? 0) + 1);
    const from = byId.get(e.source);
    const to = byId.get(e.target);
    if (e.type === "unresolved") unresolved.push({ from: from?.path ?? e.source, to: to?.label ?? e.target });
    if (!from || !to) continue;
    const t = stat.get(to.id);
    if (from.kind === "test" && t && e.type !== "unresolved") {
      const key = `${from.id}>${to.id}`;
      if (!seenTest.has(key)) {
        seenTest.add(key);
        t.testedBy += 1;
      }
    } else if (e.type === "static" && t && stat.has(from.id)) {
      const key = `${from.id}>${to.id}`;
      if (!seenUse.has(key)) {
        seenUse.add(key);
        t.usedBy += 1;
        stat.get(from.id)!.uses += 1;
      }
    }
  }
  const perFile = [...stat.values()];
  const tested = perFile.filter((f) => f.testedBy > 0).length;
  return {
    files: perFile.length,
    tests: g.nodes.filter((n) => n.kind === "test").length,
    unknownNodes: g.nodes.filter((n) => n.kind === "unknown").length,
    edges: g.edges.length,
    edgeTypes: [...types].map(([type, count]) => ({ type, count })).sort((a, b) => b.count - a.count),
    perFile,
    hubs: [...perFile].filter((f) => f.usedBy > 0).sort((a, b) => b.usedBy - a.usedBy).slice(0, 8),
    untested: perFile.filter((f) => f.testedBy === 0 && !/__init__\.py$/.test(f.node.path)),
    reach: perFile.length ? tested / perFile.length : 0,
    unresolved,
  };
}

export interface DecisionStats {
  total: number;
  proceed: number;
  abstain: number;
  missed: number;
  labelled: number;
  abstainRate: number | null;
}

export function decisionStats(rows: DecisionRow[]): DecisionStats {
  const proceed = rows.filter((d) => d.decision === "proceed").length;
  const labelled = rows.filter((d) => d.missed != null).length;
  return {
    total: rows.length,
    proceed,
    abstain: rows.length - proceed,
    missed: rows.filter((d) => d.missed === true).length,
    labelled,
    abstainRate: rows.length ? (rows.length - proceed) / rows.length : null,
  };
}

/** Share of test files left out of a decision, 0..1. `total` is the number of test files in the recorded run. */
export function skippedShare(d: DecisionRow, total: number): number | null {
  return total > 0 ? Math.max(0, (total - d.selected.length) / total) : null;
}
