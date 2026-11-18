import type { LucideIcon } from "lucide-react";

export function Card({ title, action, children, className = "" }: {
  title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`card-shadow rise min-w-0 rounded-2xl border border-border bg-card p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-semibold tracking-tight">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, icon: Icon, children }: {
  label: React.ReactNode; value: React.ReactNode; hint?: string; icon?: LucideIcon; children?: React.ReactNode;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div className="text-xs font-medium uppercase tracking-wider text-muted">{label}</div>
        {Icon && (
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent-soft text-accent">
            <Icon size={16} aria-hidden />
          </span>
        )}
      </div>
      <div className="mt-2 text-3xl font-semibold tracking-tight">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
      {children && <div className="mt-3">{children}</div>}
    </Card>
  );
}
