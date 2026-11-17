"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Empty } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { RiskBar } from "@/components/ui/charts";
import type { DecisionRow } from "@/lib/api";

function Outcome({ d }: { d: DecisionRow }) {
  if (d.missed == null) return <Badge>pending</Badge>;
  return d.missed ? <Badge tone="red">missed</Badge> : <Badge tone="green">safe</Badge>;
}

function Row({ d }: { d: DecisionRow }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr className="border-t border-border transition hover:bg-card-2/60">
        <td className="py-3 pl-1 pr-3 text-muted tabular-nums">#{d.id}</td>
        <td className="pr-3 whitespace-nowrap text-muted">{new Date(d.recorded * 1000).toLocaleString()}</td>
        <td className="pr-3"><Badge tone={d.decision === "proceed" ? "green" : "amber"}>{d.decision}</Badge></td>
        <td className="pr-3"><RiskBar value={d.residual_risk ?? null} target={d.alpha} /></td>
        <td className="pr-3 tabular-nums">{d.selected.length}</td>
        <td className="pr-3"><Outcome d={d} /></td>
        <td className="pr-1 text-right">
          <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label={`Details of decision ${d.id}`}
            className="grid h-7 w-7 place-items-center rounded-md text-muted hover:bg-card-2 hover:text-foreground">
            <ChevronDown size={16} className={`transition ${open ? "rotate-180" : ""}`} />
          </button>
        </td>
      </tr>
      {open && (
        <tr className="bg-card-2/50">
          <td colSpan={7} className="px-4 py-4">
            <div className="grid gap-4 text-sm md:grid-cols-2">
              <div>
                <div className="mb-1.5 text-xs font-medium uppercase tracking-wider text-muted">Why</div>
                <ul className="list-disc space-y-1 pl-5">{d.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              </div>
              <div>
                <div className="mb-1.5 text-xs font-medium uppercase tracking-wider text-muted">Selected tests ({d.selected.length})</div>
                <div className="flex flex-wrap gap-1.5">
                  {d.selected.map((t) => <code key={t}>{t}</code>)}
                </div>
                <div className="mt-3 text-xs text-muted">mode {d.mode} · base <code>{d.base.slice(0, 10)}</code></div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function DecisionTable({ rows }: { rows: DecisionRow[] }) {
  if (rows.length === 0) return <Empty>No decisions yet. Run <code>codetwin select</code>.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wider text-muted">
          <tr>
            <th className="pb-2 pl-1 pr-3 font-medium">#</th><th className="pr-3 font-medium">When</th>
            <th className="pr-3 font-medium">Decision</th><th className="pr-3 font-medium">Residual risk</th>
            <th className="pr-3 font-medium">Tests</th><th className="pr-3 font-medium">Outcome</th>
            <th><span className="sr-only">Details</span></th>
          </tr>
        </thead>
        <tbody>{rows.map((d) => <Row key={d.id} d={d} />)}</tbody>
      </table>
    </div>
  );
}
