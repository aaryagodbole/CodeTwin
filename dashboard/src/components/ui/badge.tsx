const tones = {
  // Text uses the *-ink tokens (at least 4.5:1 on the tinted fill in both themes); the dot keeps the bright colour.
  green: "bg-good/15 text-good-ink",
  amber: "bg-warn/15 text-warn-ink",
  red: "bg-bad/15 text-bad-ink",
  accent: "bg-accent-soft text-accent",
  gray: "bg-muted/15 text-muted",
} as const;

export function Badge({ tone = "gray", children }: { tone?: keyof typeof tones; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {children}
    </span>
  );
}
