"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { GraphView, Legend } from "@/components/graph-view";
import { ErrorBox, Loading } from "@/components/state";
import { Card } from "@/components/ui/card";
import { get, type Graph } from "@/lib/api";

function Impact() {
  const params = useSearchParams();
  const router = useRouter();
  const file = params.get("file") ?? "";
  const lines = params.get("lines") ?? undefined;
  const q = useQuery({ queryKey: ["graph", file, lines], queryFn: () => get<Graph & { target: { id: string } }>("/graph", { file, lines }), enabled: !!file });
  if (!file) return <p className="text-sm text-muted">Pick a file on the system map.</p>;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Impact of <code>{file}{lines ? `:${lines}` : ""}</code></h1>
        <p className="text-sm text-muted">{q.data?.summary}</p>
      </div>
      <Card>
        <div className="mb-3"><Legend /></div>
        {q.error ? <ErrorBox error={q.error} /> : q.data ? (
          <GraphView graph={q.data} root={q.data.target.id}
            onOpen={(p) => p !== file && router.push(`/graph/?file=${encodeURIComponent(p)}`)} />
        ) : <Loading />}
      </Card>
      {q.data?.unknowns?.length ? (
        <Card title="What the analysis cannot see">
          <ul className="list-disc pl-5 text-sm">{q.data.unknowns.map((u) => <li key={u}>{u}</li>)}</ul>
        </Card>
      ) : null}
    </div>
  );
}

export default function ImpactPage() {
  return <Suspense fallback={<Loading />}><Impact /></Suspense>;
}
