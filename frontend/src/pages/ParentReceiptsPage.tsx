import { ListSkeleton } from '../components/ui/Skeleton';
import { Fragment, useState, useMemo } from 'react';
import { ChevronDown } from 'lucide-react';
import { ParentShell } from '../components/ParentShell';
import { DownloadReceiptLink } from '../components/DownloadReceiptLink';
import { useMyChildren } from '../hooks/useMyChildren';
import { groupReceiptRows, type ReceiptGroup } from '../lib/receiptGroups';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

function Breakdown({ row }: { row: ReceiptGroup }) {
  return (
    <ul className="mt-2 rounded-md bg-ink-100 divide-y divide-ink-200" aria-label={`Breakdown of ${formatCurrency(row.total)} payment`}>
      {row.slices.map((sl) => (
        <li key={sl.paymentId} className="flex items-center justify-between gap-3 px-3 py-2">
          <span className="text-xs text-ink-700 min-w-0 truncate">
            {sl.invoiceLabel} · <span className="figure">{formatCurrency(sl.amount)}</span>
          </span>
          <DownloadReceiptLink paymentId={sl.paymentId} />
        </li>
      ))}
    </ul>
  );
}

function SplitToggle({ row, open, onToggle }: { row: ReceiptGroup; open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:underline"
    >
      Split across {row.slices.length} invoices
      <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
    </button>
  );
}

export function ParentReceiptsPage() {
  const { children, loading, error } = useMyChildren();
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);

  // Most-recent-first, one entry per payment the parent actually made. A payment that was
  // split across several invoices is ONE entry with a breakdown (see lib/receiptGroups.ts).
  const rows = useMemo(() => groupReceiptRows(children, selectedChildId), [children, selectedChildId]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <ParentShell>
      <h1 className="font-display text-xl sm:text-2xl text-ink-900 font-medium mb-1">Receipts</h1>
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
              !selectedChildId ? 'bg-emerald-100 text-emerald-700 border-emerald-700' : 'border-ink-200 text-ink-600 hover:bg-ink-100'
            }`}
          >
            All children
          </button>
          {children.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedChildId(c.id)}
              className={`text-xs font-medium px-3 py-1.5 rounded-full border ${
                selectedChildId === c.id ? 'bg-emerald-100 text-emerald-700 border-emerald-700' : 'border-ink-200 text-ink-600 hover:bg-ink-100'
              }`}
            >
              {c.full_name}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <ListSkeleton rows={3} />
      ) : rows.length === 0 ? (
        <div className="bg-panel border border-ink-200 rounded-lg px-6 py-12 text-center">
          <p className="text-sm text-ink-600">No confirmed payments yet.</p>
        </div>
      ) : (
        <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden">
          <ul className="md:hidden divide-y divide-ink-200">
            {rows.map((r) => (
              <li key={r.key} className="px-4 py-3.5">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="figure text-sm text-ink-900">{formatCurrency(r.total)}</p>
                    <p className="text-xs text-ink-600 mt-0.5 truncate">
                      {r.childName} · {r.method}
                    </p>
                    <p className="text-xs text-ink-400 mt-0.5">{r.paidAt ? new Date(r.paidAt).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}</p>
                  </div>
                  {r.slices.length === 1 ? <DownloadReceiptLink paymentId={r.slices[0].paymentId} /> : <SplitToggle row={r} open={expanded.has(r.key)} onToggle={() => toggle(r.key)} />}
                </div>
                {r.slices.length > 1 && expanded.has(r.key) && <Breakdown row={r} />}
              </li>
            ))}
          </ul>
          <div className="ledger-lines overflow-x-auto hidden md:block">
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
                <Fragment key={r.key}>
                  <tr className="h-10 text-ink-900">
                    <td className="px-5">{r.paidAt ? new Date(r.paidAt).toLocaleDateString('en-KE') : '—'}</td>
                    <td className="px-5">{r.childName}</td>
                    <td className="px-5 text-ink-600">{r.method}</td>
                    <td className="px-5 figure text-right">{formatCurrency(r.total)}</td>
                    <td className="px-5">
                      {r.slices.length === 1 ? <DownloadReceiptLink paymentId={r.slices[0].paymentId} /> : <SplitToggle row={r} open={expanded.has(r.key)} onToggle={() => toggle(r.key)} />}
                    </td>
                  </tr>
                  {r.slices.length > 1 && expanded.has(r.key) && (
                    <tr>
                      <td colSpan={5} className="px-5 pb-3">
                        <Breakdown row={r} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}
    </ParentShell>
  );
}
