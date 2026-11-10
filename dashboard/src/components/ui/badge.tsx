const tones = {
  green: "bg-green-500/15 text-green-600 dark:text-green-400",
  amber: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  red: "bg-red-500/15 text-red-600 dark:text-red-400",
  gray: "bg-zinc-500/15 text-zinc-600 dark:text-zinc-400",
} as const;

export function Badge({ tone = "gray", children }: { tone?: keyof typeof tones; children: React.ReactNode }) {
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}
