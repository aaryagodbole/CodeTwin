"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock, Database, GitCommit, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { DecisionTable } from "@/app/decisions/table";
import { ErrorBox, Loading } from "@/components/state";
import { Card, Stat } from "@/components/ui/card";
import { Donut, RiskGauge, Sparkline } from "@/components/ui/charts";
import { get, type Calibration, type DecisionRow, type Summary } from "@/lib/api";

const pct = (x: number | null | undefined) => (x == null ? "–" : `${(x * 100).toFixed(1)}%`);

export default function Overview() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => get<Summary>("/summary") });
  const decisions = useQuery({ queryKey: ["decisions", 10], queryFn: () => get<DecisionRow[]>("/decisions", { limit: "10" }) });
  const calibration = useQuery({ queryKey: ["calibration"], queryFn: () => get<Calibration>("/calibration") });
  if (summary.error) return <ErrorBox error={summary.error} />;
  if (!summary.data) return <Loading />;
  const s = summary.data;
  const rows = decisions.data ?? [];
  const latest = rows[0];
  const chrono = [...rows].reverse();
  const proceed = rows.filter((d) => d.decision === "proceed").length;
  const missed = rows.filter((d) => d.missed === true).length;
  const pending = rows.filter((d) => d.missed == null).length;
  const safe = rows.length - missed - pending;
  const observed = calibration.data?.points.map((p) => p.observed_miss_rate) ?? [];
  const rate = calibration.data && calibration.data.labelled ? calibration.data.misses / calibration.data.labelled : null;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-sm text-muted">{s.root} · packages {s.packages.join(", ") || "–"}</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Latest residual risk" className="lg:row-span-1">
          <RiskGauge value={latest ? (latest.residual_risk ?? null) : null} target={s.alpha} />
          <p className="mt-1 text-center text-xs text-muted">
            {latest ? `Decision #${latest.id} · ${latest.decision}` : "No decision yet"}
          </p>
        </Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
          <Stat label="Observed miss rate" value={pct(rate)} hint={`target ${pct(s.alpha)} · level ${pct(s.alpha_t)}`} icon={ShieldCheck}>
            <Sparkline values={observed} />
          </Stat>
          <Stat label="Decisions" value={s.decisions} hint={`${s.labelled_decisions} with known outcome`} icon={Database}>
            <Sparkline values={chrono.map((d) => d.residual_risk ?? 0)} color="var(--accent-2)" />
          </Stat>
          <Stat label="Recorded commit" value={<code className="text-xl">{s.recorded_commit?.slice(0, 8) ?? "none"}</code>}
            hint={`${s.test_files} test files`} icon={GitCommit} />
          <Stat label="Full suite time" value={s.suite_seconds == null ? "–" : `${s.suite_seconds.toFixed(1)}s`}
            hint={`calibration set: ${s.calibration_size} changes`} icon={Clock} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Recent outcomes">
          <Donut parts={[
            { label: "Safe", value: safe, color: "var(--good)" },
            { label: "Missed", value: missed, color: "var(--bad)" },
            { label: "Pending", value: pending, color: "var(--muted)" },
          ]} />
          <p className="mt-4 text-xs text-muted">{proceed} of the last {rows.length} decisions proceeded; the rest abstained and ran more tests.</p>
        </Card>
        <Card title="Latest decisions" className="lg:col-span-2"
          action={<Link href="/decisions/" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">All decisions <ArrowRight size={13} /></Link>}>
          {decisions.error ? <ErrorBox error={decisions.error} /> : decisions.data ? <DecisionTable rows={rows} /> : <Loading />}
        </Card>
      </div>
    </div>
  );
}
