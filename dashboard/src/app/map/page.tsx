"use client";

import { useQuery } from "@tanstack/react-query";
import { FileCode2, FlaskConical, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
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

const chip = "inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-border bg-card-2 px-3 py-1 text-xs";

export default function SystemMap() {
  const router = useRouter();
  const q = useQuery({ queryKey: ["map"], queryFn: () => get<Graph>("/map") });
  // Big graphs start without runtime links (one per test and file reached) so the structure is readable; the user can switch them on.
  const [picked_types, setTypes] = useState<string[] | null>(null);
  const types = picked_types ?? (q.data && q.data.edges.length > 150 ? TYPES.map((t) => t.key).filter((k) => k !== "runtime") : TYPES.map((t) => t.key));
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
  const node = graph?.nodes.find((n) => n.id === picked);
  const related = node && graph ? graph.edges.filter((e) => e.source === node.id || e.target === node.id) : [];
  const label = (id: string) => graph?.nodes.find((n) => n.id === id)?.path ?? id;
  return (
    <div className="space-y-6">
      <PageHeader title="Dependency graph">
        Every source file and test, and how each link is known. Hover a node to light up its neighbours, click it for details, double-click to open its impact view.
      </PageHeader>
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <label className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find a file or test"
              aria-label="Find a file or test"
              className="w-56 rounded-full border border-border bg-card-2 py-1.5 pl-8 pr-3 text-sm outline-none focus:border-accent" />
          </label>
          {TYPES.map((t) => (
            <label key={t.key} className={chip}>
              <input type="checkbox" className="accent-[var(--accent)]" checked={types.includes(t.key)}
                onChange={(e) => setTypes(e.target.checked ? [...types, t.key] : types.filter((x) => x !== t.key))} />
              {t.key}
              <Info label={`What is a ${t.key} link?`}>{t.hint}</Info>
            </label>
          ))}
          <label className={chip}>
            <input type="checkbox" className="accent-[var(--accent)]" checked={tests} onChange={(e) => setTests(e.target.checked)} /> tests
          </label>
        </div>
        <div className="mb-3"><Legend /></div>
        {q.error ? <ErrorBox error={q.error} /> : graph ? (
          graph.nodes.length === 0 ? <Empty>Nothing recorded yet. Run <code>codetwin record</code>.</Empty> : (
            <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
              <GraphView graph={graph} onOpen={onOpen} onSelect={onSelect} search={search} />
              <aside className="rounded-xl border border-border bg-card-2/40 p-4 text-sm" aria-live="polite">
                {node ? (
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 font-medium">
                        {node.kind === "test" ? <FlaskConical size={16} className="text-good" /> : <FileCode2 size={16} className="text-accent" />}
                        <span className="break-all">{node.path}</span>
                      </div>
                      <button onClick={() => setPicked(null)} aria-label="Close details" className="text-muted hover:text-foreground"><X size={16} /></button>
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
                    {node.kind !== "test" && (
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
