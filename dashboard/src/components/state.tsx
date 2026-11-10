// Loading and error states shared by every page.
export function Loading() {
  return <p className="text-sm text-muted">Loading…</p>;
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm">
      <strong>Could not reach the CodeTwin API.</strong> Start it with <code>codetwin serve</code> in your project.
      <div className="mt-1 text-muted">{String((error as Error)?.message ?? error)}</div>
    </div>
  );
}
