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
  const graph = useMemo(() => {
    if (!q.data) return undefined;
    const nodes = q.data.nodes.filter((n) => tests || n.kind !== "test");
    const ids = new Set(nodes.map((n) => n.id));
    const edges = q.data.edges.filter((e) => types.includes(e.type) && ids.has(e.source) && ids.has(e.target));
    return { nodes, edges };
  }, [q.data, types, tests]);
  const onOpen = useCallback((p: string) => { if (p !== "?") router.push(`/graph/?file=${encodeURIComponent(p)}`); }, [router]);
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
        Every source file and test, and how each link is known. Hover a node to light up its neighbours, click it for details, double-click to open its impact view.
      </PageHeader>
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
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
            <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
              <GraphView graph={graph} onOpen={onOpen} onSelect={onSelect} search={search} selected={picked} />
              <aside className="rounded-xl border border-border bg-card-2/40 p-4 text-sm" aria-live="polite">
                {node ? (
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 font-medium">
                        {node.kind === "test" ? <FlaskConical size={16} className="text-good" /> : <FileCode2 size={16} className="text-accent" />}
                        <span className="break-all">{node.path}</span>
                      </div>
                      <button onClick={closeDetails} aria-label="Close details" className="text-muted hover:text-foreground"><X size={16} /></button>
                    </div>
                    <p className="text-xs text-muted">{node.kind === "test" ? "Test file" : "Source file"} · {related.length} links</p>
                    <ul className="max-h-60 space-y-1.5 overflow-y-auto text-xs">
                      {related.map((e, i) => (
                        <li key={i} className="rounded-lg bg-card px-2.5 py-1.5">
                          <span className="text-muted">{e.type}</span>{" "}
                          {e.source === node.id ? "→ " : "← "}
                          <span className="break-all">{label(e.source === node.id ? e.target : e.source)}</span>
                        </li>
                      ))}
                    </ul>
                    {(node.kind === "source" || node.kind === "target") && (
                      <button onClick={() => onOpen(node.path)} className="w-full rounded-lg bg-accent px-3 py-2 text-xs font-medium text-white hover:opacity-90">
                        See what a change here affects
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="text-muted">Click a file or test to see what it is connected to.</p>
                )}
              </aside>
            </div>
          )
        ) : <Loading />}
      </Card>
    </div>
  );
}
