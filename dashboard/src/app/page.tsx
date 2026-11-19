"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Database, FolderTree, GitCommit, Network, ShieldCheck, Zap } from "lucide-react";
import Link from "next/link";
import { DecisionTable } from "@/app/decisions/table";
import { ErrorBox, Loading } from "@/components/state";
import { Card, Stat } from "@/components/ui/card";
import { Donut, fmtPct, RiskGauge, Sparkline } from "@/components/ui/charts";
import { Info } from "@/components/ui/info";
import { skippedShare } from "@/lib/analysis";
import { get, type Calibration, type DecisionRow, type Summary } from "@/lib/api";

const pct = (x: number | null | undefined) => (x == null ? "–" : fmtPct(x));

export default function Overview() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => get<Summary>("/summary") });
  const decisions = useQuery({ queryKey: ["decisions", 10], queryFn: () => get<DecisionRow[]>("/decisions", { limit: "10" }) });
  const calibration = useQuery({ queryKey: ["calibration"], queryFn: () => get<Calibration>("/calibration") });
  if (summary.error) return <ErrorBox error={summary.error} />;
  if (!summary.data) return <Loading />;
  const s = summary.data;
  const rows = decisions.data ?? [];
  // Decision cards wait for their own request: an empty list before it answers is not "no decisions".
  const decisionState = decisions.error ? <ErrorBox error={decisions.error} /> : !decisions.data ? <Loading /> : null;
  const latest = rows[0];
  const chrono = [...rows].reverse();
  const proceed = rows.filter((d) => d.decision === "proceed").length;
  const missed = rows.filter((d) => d.missed === true).length;
  const pending = rows.filter((d) => d.missed == null).length;
  const safe = rows.length - missed - pending;
  // Only decisions against the recording whose suite size we know (see skippedShare).
  const shares = rows.map((d) => skippedShare(d, s.test_files, s.recorded_commit)).filter((x): x is number => x != null);
  const avgSkipped = shares.length ? shares.reduce((a, b) => a + b, 0) / shares.length : null;
  const observed = calibration.data?.points.map((p) => p.observed_miss_rate) ?? [];
  const rate = calibration.data && calibration.data.labelled ? calibration.data.misses / calibration.data.labelled : null;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-sm text-muted">{s.root} · packages {s.packages.join(", ") || "–"}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { href: "/map/", icon: Network, title: "Dependency graph", text: "See how files and tests connect" },
          { href: "/repository/", icon: FolderTree, title: "Repository analysis", text: "Hubs, untested files, unknowns" },
          { href: "/decisions/", icon: Database, title: "Decisions", text: "Why each change got its tests" },
        ].map(({ href, icon: Icon, title, text }) => (
          <Link key={href} href={href} className="card-shadow group flex items-center gap-3 rounded-2xl border border-border bg-card p-4 transition hover:border-accent">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent-soft text-accent"><Icon size={18} aria-hidden /></span>
            <span className="min-w-0"><span className="block text-sm font-semibold">{title}</span><span className="block truncate text-xs text-muted">{text}</span></span>
            <ArrowRight size={16} className="ml-auto text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden />
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Latest residual risk" action={<Info align="end">The estimated chance that a test the change affects is among those skipped. Above the target, CodeTwin abstains and recommends a broader selection.</Info>}>
          {decisionState ?? (<>
            {/* The target this decision was made with (its recorded alpha), not today's configuration. */}
            <RiskGauge value={latest ? (latest.residual_risk ?? null) : null} target={latest ? latest.alpha : null} />
            <p className="mt-1 text-center text-xs text-muted">
              {latest ? `Decision #${latest.id} · ${latest.decision}` : "No decision yet"}
            </p>
          </>)}
        </Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
          <Stat label="Observed miss rate" value={calibration.error ? "error" : pct(rate)}
            hint={calibration.error ? "could not load calibration"
              : `target ${pct(s.alpha)} · level ${pct(s.alpha_t)} · calibrated on ${s.calibration_size} labelled changes`} icon={ShieldCheck}>
            {calibration.error ? <p className="text-xs text-bad-ink">{String(calibration.error.message ?? calibration.error)}</p> : <Sparkline values={observed} />}
          </Stat>
          <Stat label="Decisions" value={s.decisions} hint={`${s.labelled_decisions} with known outcome`} icon={Database}>
            <Sparkline values={chrono.map((d) => d.residual_risk ?? null)} color="var(--accent-2)" />
          </Stat>
          <Stat label="Recorded commit" value={<code className="text-xl">{s.recorded_commit?.slice(0, 8) ?? "none"}</code>}
            hint={`${s.test_files} test files`} icon={GitCommit} />
          <Stat label={<>Test files skipped <Info>Average share of test files left out of a run, over the latest decisions made against the current recording. An estimate of effort saved; it assumes similar test durations.</Info></>}
            value={decisions.error ? "error" : !decisions.data ? "…" : avgSkipped == null ? "–" : `${(avgSkipped * 100).toFixed(0)}%`}
            hint={s.suite_seconds == null ? "estimate" : `full suite takes ${s.suite_seconds.toFixed(1)}s`} icon={Zap} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Recent outcomes">
          {decisionState ?? (<>
            <Donut parts={[
              { label: "Safe", value: safe, color: "var(--good)" },
              { label: "Missed", value: missed, color: "var(--bad)" },
              { label: "Pending", value: pending, color: "var(--muted)" },
            ]} />
            <p className="mt-4 text-xs text-muted">{proceed} of the last {rows.length} decisions proceeded; the rest abstained and recommended a broader selection.</p>
          </>)}
        </Card>
        <Card title="Latest decisions" className="lg:col-span-2"
          action={<Link href="/decisions/" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">All decisions <ArrowRight size={13} /></Link>}>
          {decisions.error ? <ErrorBox error={decisions.error} /> : decisions.data ? <DecisionTable rows={rows} /> : <Loading />}
        </Card>
      </div>
    </div>
  );
}
