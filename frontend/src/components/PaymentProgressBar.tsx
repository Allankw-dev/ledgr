interface PaymentProgressBarProps {
  totalDue: number;
  totalPaid: number;
}

/**
 * Visual paid-vs-outstanding bar for a single child, summed across all of
 * their invoices. Purely presentational — takes already-fetched totals
 * rather than re-deriving them, so it stays in sync with whatever the
 * caller computed for the balance figure above it.
 */
export function PaymentProgressBar({ totalDue, totalPaid }: PaymentProgressBarProps) {
  const safeTotal = totalDue > 0 ? totalDue : 0;
  const paidPct = safeTotal === 0 ? 100 : Math.min(100, Math.round((totalPaid / safeTotal) * 100));

  return (
    <div className="px-5 pb-4">
      <div className="flex items-center justify-between text-xs text-ink-600 mb-1.5">
        <span>{paidPct}% paid</span>
        <span>
          {new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(totalPaid)}
          {' of '}
          {new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(safeTotal)}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-ink-100 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${paidPct >= 100 ? 'bg-emerald-500' : 'bg-amber-500'}`}
          style={{ width: `${paidPct}%` }}
        />
      </div>
    </div>
  );
}
