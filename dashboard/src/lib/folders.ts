// Folder view of the dependency graph: one node per folder, one edge per (folder, folder, link type) that
// stands for every file link between them. Display only; the links themselves come from the API.
import type { Graph, GraphEdge, GraphNode } from "@/lib/api";

export function folderOf(path: string): string {
  const i = path.lastIndexOf("/");
  return i > 0 ? path.slice(0, i) : ".";
}

export function folderGraph(g: Graph): Graph {
  const files = new Map<string, { n: number; tests: number }>();
  const folderOfNode = new Map<string, string>();
  for (const n of g.nodes) {
    if (n.kind === "unknown") {
      folderOfNode.set(n.id, n.id);
      continue;
    }
    const f = folderOf(n.path);
    folderOfNode.set(n.id, f);
    const c = files.get(f) ?? { n: 0, tests: 0 };
    c.n += 1;
    if (n.kind === "test") c.tests += 1;
    files.set(f, c);
  }
  const nodes: GraphNode[] = [...files].map(([f, c]) => ({
    id: f, path: f, files: c.n,
    label: `${f === "." ? "(root)" : f.split("/").slice(-2).join("/")} · ${c.n}`,
    // a folder of tests only is drawn as tests; anything else as a module
    kind: c.tests === c.n ? "test" : "module",
  }));
  for (const n of g.nodes) if (n.kind === "unknown") nodes.push(n);
  const weight = new Map<string, GraphEdge>();
  for (const e of g.edges) {
    const a = folderOfNode.get(e.source), b = folderOfNode.get(e.target);
    if (!a || !b || a === b) continue;          // links inside a folder show in the Files view
    const key = `${a}\u0000${b}\u0000${e.type}`;
    const cur = weight.get(key);
    if (cur) cur.weight = (cur.weight ?? 1) + 1;
    else weight.set(key, { source: a, target: b, type: e.type, weight: 1 });
  }
  return { nodes, edges: [...weight.values()] };
}

/** The files of one folder and the files they link to (one step), for the Files view of a big repository. */
export function folderScope(g: Graph, folder: string): Graph {
  const inside = new Set(g.nodes.filter((n) => n.kind !== "unknown" && folderOf(n.path) === folder).map((n) => n.id));
  const edges = g.edges.filter((e) => inside.has(e.source) || inside.has(e.target));
  const keep = new Set([...inside, ...edges.flatMap((e) => [e.source, e.target])]);
  return { nodes: g.nodes.filter((n) => keep.has(n.id)), edges };
}

/** Folders that hold files, biggest first. */
export function folderList(g: Graph): { folder: string; files: number }[] {
  const count = new Map<string, number>();
  for (const n of g.nodes) if (n.kind !== "unknown") count.set(folderOf(n.path), (count.get(folderOf(n.path)) ?? 0) + 1);
  return [...count].map(([folder, files]) => ({ folder, files })).sort((a, b) => b.files - a.files || a.folder.localeCompare(b.folder));
}
