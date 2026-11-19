"use client";

import { useQuery } from "@tanstack/react-query";
import { Cloud, FlaskConical } from "lucide-react";
import { DATA_MODE, PROJECT, type DemoMeta } from "@/lib/api";

interface SnapshotMeta {
  generated: string;
  project: string;
  commit: string;
  recorded: boolean;
}

async function meta<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

// Says where the numbers come from, so a snapshot is never mistaken for live data and live data is never doubted.
export function DemoBanner() {
  const demo = useQuery({ queryKey: ["demo-meta"], queryFn: () => meta<DemoMeta>("/demo/meta.json"),
    enabled: DATA_MODE === "demo", retry: false });
  const snap = useQuery({ queryKey: ["snapshot-meta"], queryFn: () => meta<SnapshotMeta>("/snapshot/meta.json"),
    enabled: DATA_MODE === "cloud", retry: false });
  if (DATA_MODE === "live") return null;
  const frame = (icon: React.ReactNode, body: React.ReactNode) => (
    <div className="border-b border-accent/20 bg-accent-soft text-sm">
      <div className="mx-auto flex max-w-6xl items-start gap-2 px-4 py-2 text-foreground/80 md:px-8">{icon}<span>{body}</span></div>
    </div>
  );
  if (DATA_MODE === "cloud") {
    const s = snap.data;
    return frame(<Cloud size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden />, <>
      Live data for <code>{PROJECT}</code>: decisions, risk and calibration are the reports its CI uploads to CodeTwin
      Cloud on every pull request.
      {s ? <> The dependency graph is from commit <code>{s.commit.slice(0, 10)}</code> ({new Date(s.generated).toLocaleDateString()}
        {s.recorded ? ", with runtime links from a full test run" : ", static links only"}).</> : null}
    </>);
  }
  const when = demo.data ? new Date(demo.data.generated).toLocaleDateString() : "";
  return frame(<FlaskConical size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden />, <>
    Demo data: a real CodeTwin run on <code>{demo.data?.project ?? "examples/python"}</code>
    {demo.data ? ` (${demo.data.edits} labelled changes, generated ${when})` : ""}. Run{" "}
    <code>codetwin serve</code> and the dashboard locally to see your own project.
  </>);
}
