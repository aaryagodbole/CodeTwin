// Small hand-drawn SVG charts (no extra dependency): risk gauge, sparkline, bar and donut.
import { useId } from "react";

/** Upper end of a risk scale: at least `min`, growing in steps of 10 points to fit both the risk and the target,
 *  so neither is pinned to the end. Shared by the gauge and the bar. */
export function riskScale(value: number | null | undefined, target: number | null | undefined, min = 0.5): number {
  return Math.min(1, Math.max(min, Math.ceil(Math.max(value ?? 0, target ?? 0) * 10 + 0.0001) / 10));
}

/** Semicircle gauge: the arc fills to `value`, a tick marks `target`. Both are fractions (0..1). */
export function RiskGauge({ value, target, max: minMax = 0.5 }: { value: number | null; target: number | null; max?: number }) {
  const max = riskScale(value, target, minMax);
  const gradient = useId();      // unique per gauge: two gauges on one page must not share a gradient id
  const r = 80;
  const cx = 100;
  const cy = 100;
  const len = Math.PI * r;
  const frac = (x: number) => Math.max(0, Math.min(1, x / max));
  const point = (x: number, rad: number) => {
    const a = Math.PI * (1 - frac(x));
    return [cx + rad * Math.cos(a), cy - rad * Math.sin(a)];
  };
  const arc = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
  const over = value != null && target != null && value > target;
  const [tx1, ty1] = target == null ? [0, 0] : point(target, r - 14);
  const [tx2, ty2] = target == null ? [0, 0] : point(target, r + 10);
  return (
    <svg viewBox="0 0 200 120" className="w-full" role="img"
      aria-label={`${value == null ? "No residual risk yet" : `Residual risk ${fmtPct(value)}`}${
        target == null ? "" : `, target ${fmtPct(target)}${value != null && value > target ? ", above target" : ""}`}`}>
      <defs>
        <linearGradient id={gradient} x1="0" x2="1">
          <stop offset="0%" stopColor="var(--accent)" />
          <stop offset="100%" stopColor="var(--accent-2)" />
        </linearGradient>
      </defs>
      <path d={arc} fill="none" stroke="var(--card-2)" strokeWidth="16" strokeLinecap="round" />
      {value != null && (
        <path d={arc} fill="none" stroke={over ? "var(--bad)" : `url(#${gradient})`} strokeWidth="16" strokeLinecap="round"
          strokeDasharray={`${len * frac(value)} ${len}`} style={{ transition: "stroke-dasharray 0.6s ease" }} />
      )}
      {target != null && <line x1={tx1} y1={ty1} x2={tx2} y2={ty2} stroke="var(--foreground)" strokeWidth="2.5" strokeLinecap="round" />}
      <text x={cx} y={cy - 12} textAnchor="middle" fontSize="28" fontWeight="600" fill="var(--foreground)">
        {value == null ? "–" : fmtPct(value)}
      </text>
      <text x={cx} y={cy + 8} textAnchor="middle" fontSize="9" fill="var(--muted)">
        {target == null ? "residual risk" : `residual risk · target ${fmtPct(target)}`}
      </text>
    </svg>
  );
}

/** "12.5%" or "10%": every percentage on the dashboard goes through this, so one value never reads 12.5% in one
 *  place and 13% in another. */
export const fmtPct = (x: number) => `${Number((x * 100).toFixed(1))}%`;

/** A small trend line. `null` is an unknown value and leaves a gap; it is never drawn as zero. */
export function Sparkline({ values, color = "var(--accent)", height = 36 }: { values: (number | null)[]; color?: string; height?: number }) {
  const known = values.filter((v): v is number => v != null);
  if (values.length < 2 || known.length < 2) return <div style={{ height }} className="rounded-lg bg-card-2" aria-hidden />;
  const w = 120;
  const lo = Math.min(...known);
  const hi = Math.max(...known);
  const span = hi - lo || 1;
  const x = (i: number) => (i / (values.length - 1)) * w;
  const y = (v: number) => height - 4 - ((v - lo) / span) * (height - 8);
  // Split into runs of known values; each run is its own line (and area), so unknowns show as gaps.
  const runs: [number, number][][] = [];
  values.forEach((v, i) => {
    if (v == null) return;
    if (i === 0 || values[i - 1] == null) runs.push([]);
    runs[runs.length - 1].push([x(i), y(v)]);
  });
  const path = (pts: [number, number][]) => pts.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)} ${py.toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="none" aria-hidden>
      {runs.filter((r) => r.length > 1).map((r, i) => (
        <path key={`a${i}`} d={`${path(r)} L ${r[r.length - 1][0]} ${height} L ${r[0][0]} ${height} Z`} fill={color} opacity="0.12" />
      ))}
      {runs.map((r, i) => r.length > 1
        ? <path key={`l${i}`} d={path(r)} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        : <circle key={`p${i}`} cx={r[0][0]} cy={r[0][1]} r="1.5" fill={color} />)}
    </svg>
  );
}

/** Horizontal bar for a fraction of a scale, with an optional target marker. */
export function RiskBar({ value, target, max: minMax = 0.5 }: { value: number | null; target?: number | null; max?: number }) {
  const max = riskScale(value, target, minMax);
  const targetText = target == null ? null : <span className="whitespace-nowrap text-xs text-muted">target {fmtPct(target)}</span>;
  if (value == null) return <span className="text-muted">– {targetText && <> · {targetText}</>}</span>;
  const pct = Math.max(2, Math.min(100, (value / max) * 100));
  const over = target != null && value > target;
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-2 w-24 overflow-hidden rounded-full bg-card-2">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: over ? "var(--bad)" : "var(--good)" }} />
        {target != null && <div className="absolute inset-y-0 w-0.5 bg-foreground/60" style={{ left: `${Math.min(100, (target / max) * 100)}%` }} />}
      </div>
      <span className="w-12 text-right tabular-nums text-xs">{fmtPct(value)}</span>
      {targetText}
    </div>
  );
}

export function Donut({ parts }: { parts: { label: string; value: number; color: string }[] }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  const r = 40;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex items-center gap-5">
      <svg viewBox="0 0 100 100" className="h-28 w-28 -rotate-90" role="img" aria-label="Decision split">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--card-2)" strokeWidth="12" />
        {total > 0 && parts.map((p) => {
          const dash = (p.value / total) * c;
          const el = (
            <circle key={p.label} cx="50" cy="50" r={r} fill="none" stroke={p.color} strokeWidth="12"
              strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={-offset} />
          );
          offset += dash;
          return el;
        })}
      </svg>
      <ul className="space-y-1.5 text-sm">
        {parts.map((p) => (
          <li key={p.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: p.color }} aria-hidden />
            <span className="text-muted">{p.label}</span>
            <span className="ml-auto pl-4 font-medium tabular-nums">{p.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
