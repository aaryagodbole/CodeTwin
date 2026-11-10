import { Badge } from "@/components/ui/badge";
import type { DecisionRow } from "@/lib/api";

export function DecisionTable({ rows }: { rows: DecisionRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted">No decisions yet. Run <code>codetwin select</code>.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-muted">
          <tr>
            <th className="py-2 pr-4">#</th><th className="pr-4">When</th><th className="pr-4">Decision</th>
            <th className="pr-4">Residual risk</th><th className="pr-4">Target</th><th className="pr-4">Tests</th>
            <th className="pr-4">Outcome</th><th>Reasons</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.id} className="border-t border-border align-top">
              <td className="py-2 pr-4">{d.id}</td>
              <td className="pr-4 whitespace-nowrap">{new Date(d.recorded * 1000).toLocaleString()}</td>
              <td className="pr-4"><Badge tone={d.decision === "proceed" ? "green" : "amber"}>{d.decision}</Badge></td>
              <td className="pr-4">{(d.residual_risk * 100).toFixed(1)}%</td>
              <td className="pr-4">{d.alpha == null ? "–" : `${(d.alpha * 100).toFixed(0)}%`}</td>
              <td className="pr-4">{d.selected.length}</td>
              <td className="pr-4">
                {d.missed == null ? <Badge>pending</Badge> : d.missed ? <Badge tone="red">missed</Badge> : <Badge tone="green">safe</Badge>}
              </td>
              <td className="text-xs text-muted">{d.reasons.slice(0, 2).join(" · ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
