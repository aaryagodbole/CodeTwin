"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { GraphView, Legend } from "@/components/graph-view";
import { ErrorBox, Loading } from "@/components/state";
import { Card } from "@/components/ui/card";
import { get, type Graph } from "@/lib/api";

const TYPES = ["static", "runtime", "co-change", "unresolved"];

export default function SystemMap() {
  const router = useRouter();
  const q = useQuery({ queryKey: ["map"], queryFn: () => get<Graph>("/map") });
  const [types, setTypes] = useState<string[]>(TYPES);
  const [tests, setTests] = useState(true);
  const graph = useMemo(() => {
    if (!q.data) return undefined;
    const nodes = q.data.nodes.filter((n) => tests || n.kind !== "test");
    const ids = new Set(nodes.map((n) => n.id));
    const edges = q.data.edges.filter((e) => types.includes(e.type) && ids.has(e.source) && ids.has(e.target));
    return { nodes, edges };
  }, [q.data, types, tests]);
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">System map</h1>
        <p className="text-sm text-muted">Files and tests; edges show how each link is known. Click a file to see its impact.</p>
      </div>
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-4 text-sm">
          {TYPES.map((t) => (
            <label key={t} className="inline-flex items-center gap-1">
              <input type="checkbox" checked={types.includes(t)}
                onChange={(e) => setTypes(e.target.checked ? [...types, t] : types.filter((x) => x !== t))} />
              {t}
            </label>
          ))}
          <label className="inline-flex items-center gap-1">
            <input type="checkbox" checked={tests} onChange={(e) => setTests(e.target.checked)} /> tests
          </label>
          <Legend />
        </div>
        {q.error ? <ErrorBox error={q.error} /> : graph ? (
          <GraphView graph={graph} onOpen={(p) => p !== "?" && router.push(`/graph/?file=${encodeURIComponent(p)}`)} />
        ) : <Loading />}
      </Card>
    </div>
  );
}
