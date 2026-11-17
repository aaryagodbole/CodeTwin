"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorBox, Loading } from "@/components/state";
import { Card } from "@/components/ui/card";
import { get, type DecisionRow } from "@/lib/api";
import { DecisionTable } from "./table";

const FILTERS = [
  { key: "all", label: "All", test: () => true },
  { key: "proceed", label: "Proceed", test: (d: DecisionRow) => d.decision === "proceed" },
  { key: "abstain", label: "Abstain", test: (d: DecisionRow) => d.decision === "abstain" },
  { key: "missed", label: "Missed", test: (d: DecisionRow) => d.missed === true },
] as const;

export default function Decisions() {
  const q = useQuery({ queryKey: ["decisions", 500], queryFn: () => get<DecisionRow[]>("/decisions", { limit: "500" }) });
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const active = FILTERS.find((f) => f.key === filter) ?? FILTERS[0];
  const rows = q.data?.filter(active.test);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Decisions</h1>
        <p className="text-sm text-muted">Every change CodeTwin judged: which tests to run and how much risk remains.</p>
      </div>
      {q.error ? <ErrorBox error={q.error} /> : !rows ? <Loading /> : (
        <Card action={
          <div className="flex gap-1 rounded-xl bg-card-2 p-1" role="group" aria-label="Filter decisions">
            {FILTERS.map((f) => (
              <button key={f.key} onClick={() => setFilter(f.key)} aria-pressed={filter === f.key}
                className={`rounded-lg px-3 py-1 text-xs font-medium transition ${filter === f.key ? "bg-card text-foreground shadow-sm" : "text-muted hover:text-foreground"}`}>
                {f.label}
              </button>
            ))}
          </div>
        }>
          <DecisionTable rows={rows} />
        </Card>
      )}
    </div>
  );
}
