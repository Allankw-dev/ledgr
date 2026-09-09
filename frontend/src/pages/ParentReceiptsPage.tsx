import { useState, useMemo } from 'react';
import { ParentShell } from '../components/ParentShell';
import { DownloadReceiptLink } from '../components/DownloadReceiptLink';
import { useMyChildren } from '../hooks/useMyChildren';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

export function ParentReceiptsPage() {
  const { children, loading, error } = useMyChildren();
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);

  // Flattened, most-recent-first — a parent thinks of this as "my payment
  // history", not "payments grouped by child then by invoice", so the flat
  // shape here is deliberate even though the source data is nested.
  const rows = useMemo(() => {
    return children
      .filter((c) => !selectedChildId || c.id === selectedChildId)
      .flatMap((child) =>
        child.invoices.flatMap((inv) =>
          inv.payments.map((p) => ({
            paymentId: p.id,
            childName: child.full_name,
            amount: Number(p.amount),
            method: p.method,
            paidAt: p.paid_at,
          }))
        )
      )
      .sort((a, b) => new Date(b.paidAt || 0).getTime() - new Date(a.paidAt || 0).getTime());
  }, [children, selectedChildId]);

  return (
    <ParentShell>
      <h1 className="font-display text-2xl text-ink-900 font-medium mb-1">Receipts</h1>
      <p className="text-sm text-ink-600 mb-6">Every confirmed payment, with a downloadable receipt for each.</p>

      {error && (
        <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
          {error}
        </div>
      )}

      {children.length > 1 && (
        <div className="flex gap-2 mb-5 flex-wrap">
          <button
            onClick={() => setSelectedChildId(null)}
            className={`text-xs font-medium px-3 py-1.5 rounded-full border ${
              !selectedChildId ? 'bg-ink-900 text-paper border-ink-900' : 'border-ink-200 text-ink-600 hover:bg-ink-100'
            }`}
          >
            All children
          </button>
          {children.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedChildId(c.id)}
              className={`text-xs font-medium px-3 py-1.5 rounded-full border ${
                selectedChildId === c.id ? 'bg-ink-900 text-paper border-ink-900' : 'border-ink-200 text-ink-600 hover:bg-ink-100'
              }`}
            >
              {c.full_name}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-ink-600">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="bg-white border border-ink-200 rounded-lg px-6 py-12 text-center">
          <p className="text-sm text-ink-600">No confirmed payments yet.</p>
        </div>
      ) : (
        <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
          <div className="ledger-lines overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-600">
                <th className="px-5 py-2 font-medium">Date</th>
                <th className="px-5 py-2 font-medium">Child</th>
                <th className="px-5 py-2 font-medium">Method</th>
                <th className="px-5 py-2 font-medium text-right">Amount</th>
                <th className="px-5 py-2 font-medium">Receipt</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.paymentId} className="h-10 text-ink-900">
                  <td className="px-5">{r.paidAt ? new Date(r.paidAt).toLocaleDateString('en-KE') : '—'}</td>
                  <td className="px-5">{r.childName}</td>
                  <td className="px-5 text-ink-600">{r.method}</td>
                  <td className="px-5 figure text-right">{formatCurrency(r.amount)}</td>
                  <td className="px-5">
                    <DownloadReceiptLink paymentId={r.paymentId} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}
    </ParentShell>
  );
}
