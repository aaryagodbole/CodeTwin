import { CircleHelp } from "lucide-react";

/** A small "?" that explains a term in plain words on hover or keyboard focus. */
export function Info({ children, label = "What does this mean?" }: { children: React.ReactNode; label?: string }) {
  return (
    <span className="group relative inline-flex align-middle">
      <button type="button" aria-label={label} className="text-muted transition hover:text-accent focus:text-accent focus:outline-none">
        <CircleHelp size={14} aria-hidden />
      </button>
      <span role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-64 -translate-x-1/2 rounded-xl border border-border bg-card p-3 text-xs font-normal normal-case leading-relaxed tracking-normal text-foreground shadow-lg group-focus-within:block group-hover:block">
        {children}
      </span>
    </span>
  );
}

export function PageHeader({ title, children, actions }: { title: string; children?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {children && <p className="mt-1 max-w-2xl text-sm text-muted">{children}</p>}
      </div>
      {actions}
    </div>
  );
}
