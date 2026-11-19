"use client";

import { useQuery } from "@tanstack/react-query";
import { FileCode2, FlaskConical, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useRef, useState } from "react";
import { GraphView, Legend } from "@/components/graph-view";
import { Empty, ErrorBox, Loading } from "@/components/state";
import { Card } from "@/components/ui/card";
import { Info, PageHeader } from "@/components/ui/info";
import { get, type Graph } from "@/lib/api";
import { folderGraph, folderList, folderScope } from "@/lib/folders";

const TYPES: { key: string; hint: string }[] = [
  { key: "static", hint: "Found by reading the code: one file imports another." },
  { key: "runtime", hint: "Seen when the tests ran: this test really executed that file." },
  { key: "co-change", hint: "From git history: these files often change together." },
  { key: "unresolved", hint: "The analysis could not tell (for example a dynamic call). Never treated as 'no dependency'." },
];

const chip = "inline-flex items-center gap-1.5 rounded-full border border-border bg-card-2 px-3 py-1 text-xs";
// Stable defaults: a new array on every render would rebuild the graph (and lose the view) on each keystroke.
const ALL_TYPES = TYPES.map((t) => t.key);
const WITHOUT_RUNTIME = ALL_TYPES.filter((k) => k !== "runtime");

export default function SystemMap() {
  const router = useRouter();
  const q = useQuery({ queryKey: ["map"], queryFn: () => get<Graph>("/map") });
  // Big graphs start without runtime links (one per test and file reached) so the structure is readable; the user can switch them on.
  const [picked_types, setTypes] = useState<string[] | null>(null);
  const types = picked_types ?? (q.data && q.data.edges.length > 150 ? WITHOUT_RUNTIME : ALL_TYPES);
  const [tests, setTests] = useState(true);
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  // A real repository has too many files to read at once: start with one node per folder, open a folder's files.
  const [picked_view, setView] = useState<"folders" | "files" | null>(null);
  const big = !!q.data && q.data.nodes.length > 40;
  const view = picked_view ?? (big ? "folders" : "files");
  const folders = useMemo(() => (q.data ? folderList(q.data) : []), [q.data]);
  // Files of a big repository are shown one folder at a time (with the files they link to); "" is every file.
  const [picked_scope, setScope] = useState<string | null>(null);
  const scope = picked_scope ?? (big ? folders[0]?.folder ?? "" : "");
  const graph = useMemo(() => {
    if (!q.data) return undefined;
    const nodes = q.data.nodes.filter((n) => tests || n.kind !== "test");
    const ids = new Set(nodes.map((n) => n.id));
    const edges = q.data.edges.filter((e) => types.includes(e.type) && ids.has(e.source) && ids.has(e.target));
    if (view === "folders") return folderGraph({ nodes, edges });
    return scope ? folderScope({ nodes, edges }, scope) : { nodes, edges };
  }, [q.data, types, tests, view, scope]);
  const onOpen = useCallback((p: string) => {
    if (p === "?") return;
    if (view === "folders") {                     // a folder opens as its files and their neighbours
      setView("files");
      setScope(p);
      setPicked(null);
      return;
    }
    router.push(`/graph/?file=${encodeURIComponent(p)}`);
  }, [router, view]);
  const onSelect = useCallback((id: string | null) => setPicked(id), []);
  const pathOf = useMemo(() => new Map(graph?.nodes.map((n) => [n.id, n.path]) ?? []), [graph]);
  const node = graph?.nodes.find((n) => n.id === picked);
  const related = node && graph ? graph.edges.filter((e) => e.source === node.id || e.target === node.id) : [];
  const label = (id: string) => pathOf.get(id) ?? id;
  // Keyboard path to node details: the search results are a list of buttons that select like a click does.
  const term = search.trim().toLowerCase();
  // Exact path or name first, then paths that start with the text, then any other match.
  const rank = (n: { label: string; path: string }) =>
    n.path.toLowerCase() === term || n.label.toLowerCase() === term ? 0 : n.path.toLowerCase().startsWith(term) ? 1 : 2;
  const matches = term && graph
    ? graph.nodes.filter((n) => `${n.label} ${n.path}`.toLowerCase().includes(term))
      .sort((a, b) => rank(a) - rank(b) || a.path.localeCompare(b.path)).slice(0, 8)
    : [];
  // Where keyboard focus goes back to when the details close: the result that opened them, else the search box.
  const searchRef = useRef<HTMLInputElement>(null);
  const openedFrom = useRef<string | null>(null);
  const closeDetails = () => {
    setPicked(null);
    const id = openedFrom.current;
    openedFrom.current = null;
    requestAnimationFrame(() => {
      const back = id ? document.querySelector<HTMLButtonElement>(`[data-result="${CSS.escape(id)}"]`) : null;
      (back ?? searchRef.current)?.focus();
    });
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Dependency graph">
        Every source file and test, and how each link is known. Folders shows one node per folder (thicker lines stand for
        more links); double-click a folder to see its files, and a file to open its impact view. Hover lights up neighbours.
      </PageHeader>
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div role="radiogroup" aria-label="Show" className="inline-flex rounded-full border border-border bg-card-2 p-0.5 text-xs">
            {(["folders", "files"] as const).map((v) => (
              <button key={v} type="button" role="radio" aria-checked={view === v}
                onClick={() => { setView(v); setPicked(null); }}
                className={`rounded-full px-3 py-1 capitalize ${view === v ? "bg-accent text-white" : "text-muted hover:text-foreground"}`}>
                {v}
              </button>
            ))}
          </div>
          {view === "files" && folders.length > 1 && (
            <select value={scope} onChange={(e) => { setScope(e.target.value); setPicked(null); }} aria-label="Folder"
              className="max-w-56 rounded-full border border-border bg-card-2 px-3 py-1.5 text-xs outline-none focus:border-accent">
              {folders.map((f) => <option key={f.folder} value={f.folder}>{f.folder} ({f.files})</option>)}
              <option value="">All files ({q.data?.nodes.length ?? 0})</option>
            </select>
          )}
          <label className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
            <input ref={searchRef} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find a file or test"
              aria-label="Find a file or test"
              className="w-56 rounded-full border border-border bg-card-2 py-1.5 pl-8 pr-3 text-sm outline-none focus:border-accent" />
          </label>
          {TYPES.map((t) => (
            <span key={t.key} className={chip}>
              <label className="inline-flex cursor-pointer items-center gap-1.5">
                <input type="checkbox" className="accent-[var(--accent)]" checked={types.includes(t.key)}
                  onChange={(e) => setTypes(e.target.checked ? [...types, t.key] : types.filter((x) => x !== t.key))} />
                {t.key}
              </label>
              <Info label={`What is a ${t.key} link?`}>{t.hint}</Info>
            </span>
          ))}
          <label className={`${chip} cursor-pointer`}>
            <input type="checkbox" className="accent-[var(--accent)]" checked={tests} onChange={(e) => setTests(e.target.checked)} /> tests
          </label>
        </div>
        {matches.length > 0 && (
          <ul className="mb-3 flex flex-wrap gap-1.5" aria-label="Matching files and tests">
            {matches.map((n) => (
              <li key={n.id} className="min-w-0 max-w-full">
                <button type="button" data-result={n.id} onClick={() => { openedFrom.current = n.id; setPicked(n.id); }}
                  aria-pressed={picked === n.id}
                  className="max-w-full break-all rounded-2xl border border-border bg-card px-2.5 py-1 text-left text-xs hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
                  {n.path}
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="mb-3"><Legend /></div>
        {q.error ? <ErrorBox error={q.error} /> : graph ? (
          graph.nodes.length === 0 ? (
            (q.data?.nodes.length ?? 0) > 0
              ? <Empty>Every node is hidden by the filters above. Switch a filter back on to see them.</Empty>
              : <Empty>Nothing recorded yet. Run <code>codetwin record</code>.</Empty>
          ) : (
            // The graph gets the full width; a node's details float over its top-right corner while it is selected.
            <div className="relative">
              <GraphView graph={graph} onOpen={onOpen} onSelect={onSelect} search={search} selected={picked} colourBy={q.data?.nodes} />
              <aside aria-live="polite"
                className={node ? "mt-3 rounded-xl border border-border bg-card p-4 text-sm shadow-lg lg:absolute lg:right-3 lg:top-14 lg:mt-0 lg:w-80" : "sr-only"}>
                {node ? (
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 font-medium">
                        {node.kind === "test" ? <FlaskConical size={16} className="text-good" /> : <FileCode2 size={16} className="text-accent" />}
                        <span className="break-all">{node.path}</span>
                      </div>
                      <button onClick={closeDetails} aria-label="Close details" className="text-muted hover:text-foreground"><X size={16} /></button>
                    </div>
                    <p className="text-xs text-muted">
                      {node.files ? `Folder · ${node.files} files` : node.kind === "test" ? "Test file" : "Source file"} · {related.length} links
                    </p>
                    <ul className="max-h-60 space-y-1.5 overflow-y-auto text-xs">
                      {related.map((e, i) => (
                        <li key={i} className="rounded-lg bg-card px-2.5 py-1.5">
                          <span className="text-muted">{e.type}{e.weight ? ` ×${e.weight}` : ""}</span>{" "}
                          {e.source === node.id ? "→ " : "← "}
                          <span className="break-all">{label(e.source === node.id ? e.target : e.source)}</span>
                        </li>
                      ))}
                    </ul>
                    {node.files ? (
                      <button onClick={() => onOpen(node.path)} className="w-full rounded-lg bg-accent px-3 py-2 text-xs font-medium text-white hover:opacity-90">
                        Show its files
                      </button>
                    ) : (node.kind === "source" || node.kind === "target") && (
                      <button onClick={() => onOpen(node.path)} className="w-full rounded-lg bg-accent px-3 py-2 text-xs font-medium text-white hover:opacity-90">
                        See what a change here affects
                      </button>
                    )}
                  </div>
                ) : (
                  <p>Click a file or test to see what it is connected to.</p>
                )}
              </aside>
            </div>
          )
        ) : <Loading />}
      </Card>
    </div>
  );
}
