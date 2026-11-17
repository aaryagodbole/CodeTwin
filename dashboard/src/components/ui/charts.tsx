// Small hand-drawn SVG charts (no extra dependency): risk gauge, sparkline, bar and donut.

/** Semicircle gauge: the arc fills to `value`, a tick marks `target`. Both are fractions (0..1). */
export function RiskGauge({ value, target, max = 0.5 }: { value: number | null; target: number | null; max?: number }) {
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
      aria-label={value == null ? "No residual risk yet" : `Residual risk ${(value * 100).toFixed(1)} percent`}>
      <defs>
        <linearGradient id="gauge" x1="0" x2="1">
          <stop offset="0%" stopColor="var(--accent)" />
          <stop offset="100%" stopColor="var(--accent-2)" />
        </linearGradient>
      </defs>
      <path d={arc} fill="none" stroke="var(--card-2)" strokeWidth="16" strokeLinecap="round" />
      {value != null && (
        <path d={arc} fill="none" stroke={over ? "var(--bad)" : "url(#gauge)"} strokeWidth="16" strokeLinecap="round"
          strokeDasharray={`${len * frac(value)} ${len}`} style={{ transition: "stroke-dasharray 0.6s ease" }} />
      )}
      {target != null && <line x1={tx1} y1={ty1} x2={tx2} y2={ty2} stroke="var(--foreground)" strokeWidth="2.5" strokeLinecap="round" />}
      <text x={cx} y={cy - 12} textAnchor="middle" fontSize="28" fontWeight="600" fill="var(--foreground)">
        {value == null ? "–" : `${(value * 100).toFixed(1)}%`}
      </text>
      <text x={cx} y={cy + 8} textAnchor="middle" fontSize="9" fill="var(--muted)">
        {target == null ? "residual risk" : `residual risk · target ${(target * 100).toFixed(0)}%`}
      </text>
    </svg>
  );
}

export function Sparkline({ values, color = "var(--accent)", height = 36 }: { values: number[]; color?: string; height?: number }) {
  if (values.length < 2) return <div style={{ height }} className="rounded-lg bg-card-2" aria-hidden />;
  const w = 120;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, height - 4 - ((v - lo) / span) * (height - 8)]);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="none" aria-hidden>
      <path d={`${line} L ${w} ${height} L 0 ${height} Z`} fill={color} opacity="0.12" />
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Horizontal bar for a fraction of a scale, with an optional target marker. */
export function RiskBar({ value, target, max = 0.5 }: { value: number | null; target?: number | null; max?: number }) {
  if (value == null) return <span className="text-muted">–</span>;
  const pct = Math.max(2, Math.min(100, (value / max) * 100));
  const over = target != null && value > target;
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-2 w-24 overflow-hidden rounded-full bg-card-2">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: over ? "var(--bad)" : "var(--good)" }} />
        {target != null && <div className="absolute inset-y-0 w-0.5 bg-foreground/60" style={{ left: `${Math.min(100, (target / max) * 100)}%` }} />}
      </div>
      <span className="w-12 text-right tabular-nums text-xs">{(value * 100).toFixed(1)}%</span>
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
