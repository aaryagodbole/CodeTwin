"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { DecisionTable } from "@/app/decisions/table";
import { ErrorBox, Loading } from "@/components/state";
import { Card, Stat } from "@/components/ui/card";
import { get, type DecisionRow, type Summary } from "@/lib/api";

const pct = (x: number | null | undefined) => (x == null ? "–" : `${(x * 100).toFixed(1)}%`);

export default function Overview() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => get<Summary>("/summary") });
  const decisions = useQuery({ queryKey: ["decisions", 10], queryFn: () => get<DecisionRow[]>("/decisions", { limit: "10" }) });
  if (summary.error) return <ErrorBox error={summary.error} />;
  if (!summary.data) return <Loading />;
  const s = summary.data;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Overview</h1>
        <p className="text-sm text-muted">{s.root} · packages {s.packages.join(", ") || "–"}</p>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Target miss rate" value={pct(s.alpha)} hint={`adaptive level ${pct(s.alpha_t)}`} />
        <Stat label="Recorded commit" value={s.recorded_commit?.slice(0, 10) ?? "none"} hint={`${s.test_files} test files`} />
        <Stat label="Decisions" value={s.decisions} hint={`${s.labelled_decisions} with known outcome`} />
        <Stat label="Calibration set" value={s.calibration_size} hint="labelled changes" />
      </div>
      <Card title="Latest decisions">
        {decisions.error ? <ErrorBox error={decisions.error} /> : decisions.data ? <DecisionTable rows={decisions.data} /> : <Loading />}
        <Link href="/decisions/" className="mt-3 inline-block text-sm text-muted hover:underline">All decisions →</Link>
      </Card>
    </div>
  );
}
