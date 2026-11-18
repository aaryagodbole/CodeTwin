"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Boxes, FileCode2, FlaskConical, Link2, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { Empty, ErrorBox, Loading } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Card, Stat } from "@/components/ui/card";
import { Info, PageHeader } from "@/components/ui/info";
import { analyseRepo, plural } from "@/lib/analysis";
import { get, type Graph } from "@/lib/api";

const EDGE_COLOR: Record<string, string> = {
  static: "var(--muted)", runtime: "var(--accent)", "co-change": "var(--warn)", declared: "var(--accent-2)",
  suggested: "var(--accent-2)", unresolved: "var(--bad)",
};

const open = (p: string) => `/graph/?file=${encodeURIComponent(p)}`;

export default function Repository() {
  const q = useQuery({ queryKey: ["map"], queryFn: () => get<Graph>("/map") });
  const a = useMemo(() => (q.data ? analyseRepo(q.data) : undefined), [q.data]);
  if (q.error) return <ErrorBox error={q.error} />;
  if (!a) return <Loading />;
  if (a.files === 0) return <Empty>Nothing recorded yet. Run <code>codetwin record</code> to analyse this repository.</Empty>;
  const maxEdge = Math.max(...a.edgeTypes.map((e) => e.count), 1);
  const maxUsed = Math.max(...a.hubs.map((h) => h.usedBy), 1);
  return (
    <div className="space-y-6">
      <PageHeader title="Repository analysis">
        What CodeTwin learned about this codebase: how files depend on each other, which are covered by tests, and what it cannot see.
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Source files" value={a.files} icon={FileCode2} hint="analysed from the recorded commit" />
        <Stat label="Test files" value={a.tests} icon={FlaskConical} />
        <Stat label="Links found" value={a.edges} icon={Link2} hint={`${a.edgeTypes.length} kinds of evidence`} />
        <Stat label={<>Files reached by tests <Info>Share of source files that at least one test file imports or actually ran during recording. A low number means changes there are hard to check.</Info></>}
          value={`${(a.reach * 100).toFixed(0)}%`} icon={ShieldCheck}
          hint={a.untested.length ? `${a.untested.length} without a test` : "every file has a test"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="How links are known">
          <ul className="space-y-3">
            {a.edgeTypes.map((e) => (
              <li key={e.type}>
                <div className="mb-1 flex justify-between text-sm"><span>{e.type}</span><span className="tabular-nums text-muted">{e.count}</span></div>
                <div className="h-2 overflow-hidden rounded-full bg-card-2">
                  <div className="h-full rounded-full" style={{ width: `${(e.count / maxEdge) * 100}%`, background: EDGE_COLOR[e.type] ?? "var(--accent)" }} />
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted">Static = read from the code. Runtime = seen while tests ran. Co-change = from git history. Unresolved = could not be determined.</p>
        </Card>

        <Card title="Most depended-on files" action={<Info>Files that many other files import. A change here can ripple widely, so they deserve the strongest tests.</Info>}>
          {a.hubs.length === 0 ? <Empty>No file is imported by another yet.</Empty> : (
            <ul className="space-y-3">
              {a.hubs.map((h) => (
                <li key={h.node.id}>
                  <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                    <Link href={open(h.node.path)} className="truncate hover:text-accent hover:underline">{h.node.path}</Link>
                    <span className="shrink-0 text-xs tabular-nums text-muted">{plural(h.usedBy, "importer")} · {plural(h.testedBy, "test")}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-card-2">
                    <div className="h-full rounded-full" style={{ width: `${(h.usedBy / maxUsed) * 100}%`, background: "linear-gradient(90deg, var(--accent), var(--accent-2))" }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Files without a test" action={<Badge tone={a.untested.length ? "amber" : "green"}>{a.untested.length ? `${a.untested.length} found` : "none"}</Badge>}>
          {a.untested.length === 0 ? <Empty>Every source file is reached by at least one test.</Empty> : (
            <ul className="divide-y divide-border text-sm">
              {a.untested.map((f) => (
                <li key={f.node.id} className="flex items-center justify-between gap-3 py-2">
                  <Link href={open(f.node.path)} className="truncate hover:text-accent hover:underline">{f.node.path}</Link>
                  <span className="shrink-0 text-xs text-muted">{plural(f.usedBy, "importer")}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="What the analysis cannot see" action={<Info>Links CodeTwin could not resolve, such as dynamic calls. They are reported as unknown, never treated as safe.</Info>}>
          {a.unresolved.length === 0 && a.unknownNodes === 0 ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted"><Boxes size={18} aria-hidden />Nothing unresolved in this repository.</div>
          ) : (
            <ul className="space-y-2 text-sm">
              {a.unresolved.map((u, i) => (
                <li key={i} className="flex gap-2 rounded-lg bg-bad/10 px-3 py-2">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-bad" aria-hidden />
                  <span><span className="break-all">{u.from}</span> uses something dynamic: <span className="text-muted">{u.to}</span></span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
