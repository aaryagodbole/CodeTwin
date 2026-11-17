"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Empty, ErrorBox, Loading } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Card, Stat } from "@/components/ui/card";
import { RiskGauge } from "@/components/ui/charts";
import { Info, PageHeader } from "@/components/ui/info";
import { get, type DecisionRow, type Summary } from "@/lib/api";
import { skippedShare } from "@/lib/analysis";

function Detail() {
  const id = Number(useSearchParams().get("id"));
  const rows = useQuery({ queryKey: ["decisions", 500], queryFn: () => get<DecisionRow[]>("/decisions", { limit: "500" }) });
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => get<Summary>("/summary") });
  if (rows.error) return <ErrorBox error={rows.error} />;
  if (!rows.data) return <Loading />;
  const d = rows.data.find((r) => r.id === id);
  if (!d) return <Empty>No decision with that number. <Link href="/decisions/" className="text-accent underline">Back to all decisions</Link></Empty>;
  const total = summary.data?.test_files ?? 0;
  const skip = skippedShare(d, total);
  const abstain = d.decision === "abstain";
  return (
    <div className="space-y-6">
      <Link href="/decisions/" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"><ArrowLeft size={14} /> All decisions</Link>
      <PageHeader title={`Decision #${d.id}`} actions={<Badge tone={abstain ? "amber" : "green"}>{d.decision}</Badge>}>
        {new Date(d.recorded * 1000).toLocaleString()} · base commit <code>{d.base.slice(0, 10)}</code> · mode {d.mode}
      </PageHeader>

      <div className={`flex gap-3 rounded-2xl border p-4 text-sm ${abstain ? "border-warn/40 bg-warn/10" : "border-good/40 bg-good/10"}`}>
        {abstain ? <ShieldAlert className="mt-0.5 shrink-0 text-warn" size={18} /> : <CheckCircle2 className="mt-0.5 shrink-0 text-good" size={18} />}
        <p>
          {abstain
            ? "The evidence was too weak to skip tests safely, so CodeTwin asked for a broader run instead of guessing."
            : "The risk of skipping the other tests stayed under the target, so only the selected tests need to run."}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Residual risk">
          <RiskGauge value={d.residual_risk ?? null} target={d.alpha} />
        </Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
          <Stat label={<>Tests to run <Info>Test files CodeTwin selected for this change.</Info></>} value={d.selected.length}
            hint={total ? `of ${total} test files` : undefined} />
          <Stat label={<>Tests skipped <Info>Share of test files left out. An estimate of effort saved, not of time (it assumes similar test durations).</Info></>}
            value={skip == null ? "–" : `${(skip * 100).toFixed(0)}%`} hint="estimate" />
          <Stat label="Outcome" value={d.missed == null ? "pending" : d.missed ? "missed" : "safe"}
            hint={d.missed == null ? "run codetwin learn to label it" : "from the later full run"} />
          <Stat label="Selection threshold" value={d.threshold == null ? "–" : d.threshold.toFixed(2)} hint={d.alpha == null ? undefined : `target miss rate ${(d.alpha * 100).toFixed(0)}%`} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Why CodeTwin decided this">
          <ul className="list-disc space-y-2 pl-5 text-sm">{d.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        </Card>
        <Card title={`Tests selected (${d.selected.length})`}>
          <ul className="divide-y divide-border text-sm">
            {d.selected.map((t) => <li key={t} className="py-2"><code>{t}</code></li>)}
          </ul>
        </Card>
      </div>
    </div>
  );
}

export default function DecisionDetailPage() {
  return <Suspense fallback={<Loading />}><Detail /></Suspense>;
}
