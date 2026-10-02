/** Shimmering placeholder block shown while data loads (replaces plain "Loading…" text). */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton rounded-md ${className}`} aria-hidden="true" />;
}

/** A stack of placeholder rows that mimics a list of cards / table rows. */
export function ListSkeleton({ rows = 4, className = '' }: { rows?: number; className?: string }) {
  return (
    <div className={`flex flex-col gap-3 ${className}`} role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3" style={{ animationDelay: `${i * 90}ms` }}>
          <Skeleton className="h-10 w-10 rounded-xl shrink-0" />
          <div className="flex-1 flex flex-col gap-2">
            <Skeleton className="h-3 w-2/5" />
            <Skeleton className="h-3 w-3/4" />
          </div>
          <Skeleton className="h-6 w-16 rounded-full shrink-0" />
        </div>
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}
