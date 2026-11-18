"use client";

import { EDGE_STYLES } from "@/components/graph-view";
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


const open = (p: string) => `/graph/?file=${encodeURIComponent(p)}`;

export default function Repository() {
  const q = useQuery({ queryKey: ["map"], queryFn: () => get<Graph>("/map") });
  const a = useMemo(() => (q.data ? analyseRepo(q.data) : undefined), [q.data]);
  // "<100%" below when rounding would hide an unreached file. A failed refresh keeps the last analysis on screen with a warning; only a first load that fails is an error page.
  if (q.error && !a) return <ErrorBox error={q.error} />;
  if (!a) return <Loading />;
  if (a.files === 0 && a.tests === 0 && a.edges === 0) return <Empty>Nothing recorded yet. Run <code>codetwin record</code> to analyse this repository.</Empty>;
  const maxEdge = Math.max(...a.edgeTypes.map((e) => e.count), 1);
  const maxUsed = Math.max(...a.hubs.map((h) => h.usedBy), 1);
  return (
    <div className="space-y-6">
      <PageHeader title="Repository analysis">
        What CodeTwin learned about this codebase: how files depend on each other, which are covered by tests, and what it cannot see.
      </PageHeader>
      {q.error && (
        <p role="status" className="rounded-xl border border-warn/40 bg-warn/10 px-3 py-2 text-sm">
          Could not refresh ({String((q.error as Error).message ?? q.error)}); showing the last analysis.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Source files" value={a.files} icon={FileCode2} hint="in the dependency graph" />
        <Stat label="Test and support files" value={a.tests} icon={FlaskConical} hint="tests plus fixtures, conftest" />
        <Stat label="Links found" value={a.edges} icon={Link2} hint={`${a.edgeTypes.length} kinds of evidence`} />
        <Stat label={<>Files reached by tests <Info>Share of source files that at least one test file imports or actually ran during recording. A low number means changes there are hard to check.</Info></>}
          value={a.files === 0 ? "–" : a.untested.length > 0 && a.reach >= 0.995 ? "<100%" : `${(a.reach * 100).toFixed(0)}%`}
          icon={ShieldCheck}
          hint={a.files === 0 ? "no source files to assess" : a.untested.length ? `${a.untested.length} without a test` : "every file has a test"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="How links are known">
          <ul className="space-y-3">
            {a.edgeTypes.map((e) => (
              <li key={e.type}>
                <div className="mb-1 flex justify-between text-sm"><span>{e.type}</span><span className="tabular-nums text-muted">{e.count}</span></div>
                <div className="h-2 overflow-hidden rounded-full bg-card-2">
                  <div className="h-full rounded-full" style={{ width: `${(e.count / maxEdge) * 100}%`, background: EDGE_STYLES[e.type]?.color ?? "var(--accent)" }} />
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted">Static = read from the code. Runtime = seen while tests ran. Co-change = from git history. Unresolved = could not be determined.</p>
        </Card>

        <Card title="Most depended-on files" action={<Info align="end">Files that many other files import. A change here can ripple widely, so they deserve the strongest tests.</Info>}>
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
          {a.files === 0 ? <Empty>No source files to assess.</Empty> : a.untested.length === 0 ? <Empty>Every source file is reached by at least one test.</Empty> : (
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

        <Card title="What the analysis cannot see" action={<Info align="end">Links CodeTwin could not resolve, such as dynamic calls. They are reported as unknown, never treated as safe.</Info>}>
          {a.unresolved.length === 0 ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted"><Boxes size={18} aria-hidden />Nothing unresolved in this repository.</div>
          ) : (
            <ul className="space-y-2 text-sm">
              {a.unresolved.map((u, i) => (
                <li key={i} className="flex gap-2 rounded-lg bg-bad/10 px-3 py-2">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-bad" aria-hidden />
                  <span><span className="break-all">{u.from}</span> uses something CodeTwin could not resolve{u.to ? <>: <span className="text-muted break-all">{u.to}</span></> : null}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
