"use client";

import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBox, Loading } from "@/components/state";
import { Card, Stat } from "@/components/ui/card";
import { get, type Calibration } from "@/lib/api";

export default function Results() {
  const q = useQuery({ queryKey: ["calibration"], queryFn: () => get<Calibration>("/calibration") });
  if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data) return <Loading />;
  const c = q.data;
  const data = c.points.map((p) => ({ n: p.n, observed: p.observed_miss_rate * 100, target: p.alpha * 100, level: p.alpha_t * 100 }));
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Results</h1>
        <p className="text-sm text-muted">Does the observed miss rate stay at the target? Each point is a change whose outcome is known (from <code>codetwin learn</code>).</p>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Labelled changes" value={c.labelled} />
        <Stat label="Misses" value={c.misses} />
        <Stat label="Observed miss rate" value={c.labelled ? `${((c.misses / c.labelled) * 100).toFixed(1)}%` : "–"} />
      </div>
      <Card title="Observed miss rate vs target">
        {data.length === 0 ? <p className="text-sm text-muted">No labelled decisions yet. Run <code>codetwin learn</code> after a few changes.</p> : (
          <div className="h-80">
            <ResponsiveContainer>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="n" label={{ value: "labelled changes", position: "insideBottom", offset: -4 }} />
                <YAxis unit="%" />
                <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
                <Legend />
                <Line type="monotone" dataKey="observed" name="observed miss rate" stroke="#3794ff" dot={false} />
                <Line type="stepAfter" dataKey="target" name="target α" stroke="#e8912d" strokeDasharray="5 4" dot={false} />
                <Line type="monotone" dataKey="level" name="adaptive level α_t" stroke="#8a8a8a" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}
