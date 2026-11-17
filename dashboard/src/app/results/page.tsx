"use client";

import { useQuery } from "@tanstack/react-query";
import { Crosshair, ShieldAlert, Target } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Empty, ErrorBox, Loading } from "@/components/state";
import { Card, Stat } from "@/components/ui/card";
import { get, type Calibration } from "@/lib/api";

export default function Results() {
  const q = useQuery({ queryKey: ["calibration"], queryFn: () => get<Calibration>("/calibration") });
  if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data) return <Loading />;
  const c = q.data;
  const data = c.points.map((p) => ({ n: p.n, observed: p.observed_miss_rate * 100, target: p.alpha * 100, level: p.alpha_t * 100 }));
  const rate = c.labelled ? (c.misses / c.labelled) * 100 : null;
  const target = data.at(-1)?.target ?? null;
  const ok = rate != null && target != null && rate <= target;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Results</h1>
        <p className="text-sm text-muted">
          Does the observed miss rate stay at the target? Each point is a change whose outcome is known (from <code>codetwin learn</code>).
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Labelled changes" value={c.labelled} icon={Crosshair} />
        <Stat label="Misses" value={c.misses} icon={ShieldAlert} />
        <Stat label="Observed miss rate" value={rate == null ? "–" : `${rate.toFixed(1)}%`}
          hint={target == null ? undefined : `${ok ? "within" : "above"} the ${target.toFixed(0)}% target`} icon={Target} />
      </div>
      <Card title="Observed miss rate vs target">
        {data.length === 0 ? <Empty>No labelled decisions yet. Run <code>codetwin learn</code> after a few changes.</Empty> : (
          <div className="h-80">
            <ResponsiveContainer>
              <AreaChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 8 }}>
                <defs>
                  <linearGradient id="obs" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="n" tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false}
                  label={{ value: "labelled changes", position: "insideBottom", offset: -4, fill: "var(--muted)", fontSize: 12 }} />
                <YAxis unit="%" tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`}
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, color: "var(--foreground)" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="observed" name="observed miss rate" stroke="var(--accent)" strokeWidth={2.5} fill="url(#obs)" />
                <Line type="stepAfter" dataKey="target" name="target α" stroke="var(--warn)" strokeWidth={2} strokeDasharray="5 4" dot={false} />
                <Line type="monotone" dataKey="level" name="adaptive level α_t" stroke="var(--muted)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}
