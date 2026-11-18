// Loading, empty and error states shared by every page.
import { CircleAlert, Inbox } from "lucide-react";

export function Loading() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading">
      <div className="skeleton h-8 w-48" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-28" />)}
      </div>
      <div className="skeleton h-64" />
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted">
      <Inbox size={28} aria-hidden />
      <p>{children}</p>
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="flex gap-3 rounded-2xl border border-bad/40 bg-bad/10 p-4 text-sm" role="alert">
      <CircleAlert className="mt-0.5 shrink-0 text-bad" size={18} aria-hidden />
      <div>
        <strong>Could not reach the CodeTwin API.</strong> Start it with <code>codetwin serve</code> in your project.
        <div className="mt-1 text-muted">{String((error as Error)?.message ?? error)}</div>
      </div>
    </div>
  );
}
