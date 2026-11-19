// Repository-wide analysis, derived in the browser from the read-only `/map` answer.
// Display only: no decision logic lives here (dashboard/AGENTS.md).
import type { DecisionRow, Graph, GraphNode } from "@/lib/api";

export interface FileStat {
  node: GraphNode;
  /** how many other files import it (static edges pointing at it) */
  usedBy: number;
  /** how many test files reach it (static or runtime edge from a test) */
  testedBy: number;
}

export interface RepoAnalysis {
  files: number;
  tests: number;
  edges: number;
  edgeTypes: { type: string; count: number }[];
  hubs: FileStat[];
  untested: FileStat[];
  /** share of source files reached by at least one test, 0..1 */
  reach: number;
  /** links the analysis could not resolve, as sentences */
  unresolved: { from: string; to: string | null }[];
}

/** Files under a tests folder (fixtures, typing samples, conftest) are test support, not source to be covered. */
export const isTestSupport = (path: string) => /(^|\/)(tests?|__tests__|spec)\//.test(path) || /(^|\/)conftest\.py$/.test(path);

export function analyseRepo(g: Graph): RepoAnalysis {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const stat = new Map<string, FileStat>();
  for (const n of g.nodes) {
    if ((n.kind === "source" || n.kind === "target") && !isTestSupport(n.path)) stat.set(n.id, { node: n, usedBy: 0, testedBy: 0 });
  }
  const seenUse = new Set<string>();
  const seenTest = new Set<string>();
  const types = new Map<string, number>();
  const unresolved: { from: string; to: string | null }[] = [];
  for (const e of g.edges) {
    types.set(e.type, (types.get(e.type) ?? 0) + 1);
    const from = byId.get(e.source);
    const to = byId.get(e.target);
    // What could not be resolved: the edge detail when the API gives one; the "?" placeholder node carries no name.
    if (e.type === "unresolved") unresolved.push({ from: from?.path ?? e.source, to: e.detail ?? (to && to.id !== "?" ? to.label : null) });
    if (!from || !to) continue;
    const t = stat.get(to.id);
    // Reach means the test imports the file (static) or ran it (runtime); co-change is history, not evidence of a test.
    if (from.kind === "test" && t && (e.type === "static" || e.type === "runtime")) {
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
      }
    }
  }
  const perFile = [...stat.values()];
  const tested = perFile.filter((f) => f.testedBy > 0).length;
  return {
    files: perFile.length,
    tests: g.nodes.filter((n) => n.kind === "test" || isTestSupport(n.path)).length,
    edges: g.edges.length,
    edgeTypes: [...types].map(([type, count]) => ({ type, count })).sort((a, b) => b.count - a.count),
    hubs: [...perFile].filter((f) => f.usedBy > 0).sort((a, b) => b.usedBy - a.usedBy).slice(0, 8),
    // Same set as `reach`, with no per-language exceptions: a file no test reached is listed, whatever its name.
    untested: perFile.filter((f) => f.testedBy === 0),
    reach: perFile.length ? tested / perFile.length : 0,
    unresolved,
  };
}

/** "1 importer", "2 importers" */
export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;


/** Share of test files left out of a decision, 0..1. `total` is the number of test files of the recorded run
 *  `recorded`; a decision made against another recording had another suite size, so it gets null (unknown). */
export function skippedShare(d: DecisionRow, total: number, recorded: string | null | undefined): number | null {
  if (!recorded || d.base !== recorded || total <= 0) return null;
  return Math.max(0, (total - d.selected.length) / total);
}
