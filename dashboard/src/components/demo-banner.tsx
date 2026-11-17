"use client";

import { useQuery } from "@tanstack/react-query";
import { DATA_MODE, type DemoMeta } from "@/lib/api";

// Shown only in demo mode, so a snapshot is never mistaken for a live project.
export function DemoBanner() {
  const meta = useQuery({
    queryKey: ["demo-meta"],
    queryFn: async () => (await fetch("/demo/meta.json")).json() as Promise<DemoMeta>,
    enabled: DATA_MODE === "demo",
  });
  if (DATA_MODE !== "demo") {
    return null;
  }
  const when = meta.data ? new Date(meta.data.generated).toLocaleDateString() : "";
  return (
    <div className="border-b border-border bg-foreground/5 text-sm">
      <div className="mx-auto max-w-6xl px-6 py-2 text-muted">
        Demo data: a real CodeTwin run on <code>{meta.data?.project ?? "examples/python"}</code>
        {meta.data ? ` (${meta.data.edits} labelled changes, generated ${when})` : ""}. Run{" "}
        <code>codetwin serve</code> and the dashboard locally to see your own project.
      </div>
    </div>
  );
}
