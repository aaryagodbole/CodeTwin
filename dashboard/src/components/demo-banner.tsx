"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { DATA_MODE, type DemoMeta } from "@/lib/api";

// Shown only in demo mode, so a snapshot is never mistaken for a live project.
export function DemoBanner() {
  const meta = useQuery({
    queryKey: ["demo-meta"],
    queryFn: async () => {
      const res = await fetch("/demo/meta.json");
      if (!res.ok) {
        throw new Error(`demo metadata: ${res.status} ${res.statusText}`);
      }
      return (await res.json()) as DemoMeta;
    },
    enabled: DATA_MODE === "demo",
    retry: false,
  });
  if (DATA_MODE !== "demo") {
    return null;
  }
  const when = meta.data ? new Date(meta.data.generated).toLocaleDateString() : "";
  return (
    <div className="border-b border-accent/20 bg-accent-soft text-sm">
      <div className="mx-auto flex max-w-6xl items-start gap-2 px-4 py-2 text-foreground/80 md:px-8">
        <FlaskConical size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden />
        <span>
          Demo data: a real CodeTwin run on <code>{meta.data?.project ?? "examples/python"}</code>
          {meta.data ? ` (${meta.data.edits} labelled changes, generated ${when})` : ""}. Run{" "}
          <code>codetwin serve</code> and the dashboard locally to see your own project.
        </span>
      </div>
    </div>
  );
}
