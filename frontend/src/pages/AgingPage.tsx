import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Avatar } from '../components/dx/Avatar';
import { DxCard } from '../components/dx/DxCard';
import { formatCurrency, formatKpi, pluralize } from '../components/dx/format';
import { ListSkeleton } from '../components/ui/Skeleton';
import { downloadAgingCsv, getAgingReport, type AgingBucketKey, type AgingReport } from '../api/aging';

/** One colour per bucket, mild to severe, used on the card edge, the proportion bar and the "days late" pill. */
const TONE: Record<AgingBucketKey, { bar: string; pill: string }> = {
  current: { bar: 'bg-green', pill: 'bg-green-100 text-green' },
  '1-30': { bar: 'bg-lime', pill: 'bg-lime/15 text-lime' },
  '31-60': { bar: 'bg-amber', pill: 'bg-amber-100 text-amber' },
  '61-90': { bar: 'bg-[#FF8A4C]', pill: 'bg-[#FF8A4C]/15 text-[#FF8A4C]' },
  '90+': { bar: 'bg-coral', pill: 'bg-coral-100 text-coral' },
};

export function AgingPage() {
  const [bucket, setBucket] = useState<AgingBucketKey | null>(null);
  const [report, setReport] = useState<AgingReport | null>(null);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError('');
    getAgingReport(bucket)
      .then((r) => !cancelled && setReport(r))
      .catch(() => !cancelled && setError("Couldn't load the aging report. Please try again."));
    return () => {
      cancelled = true;
    };
  }, [bucket]);

  async function handleExport() {
    setExporting(true);
    try {
      const blob = await downloadAgingCsv(bucket);
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/csv' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `aging-report${bucket ? `-${bucket}` : ''}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError("Couldn't prepare the export. Please try again.");
    } finally {
      setExporting(false);
    }
  }

  const total = report ? Number(report.total_outstanding) : 0;

  return (
    <AppShell>
      <div className="px-4 sm:px-6 xl:px-8 pt-5 sm:pt-6 pb-24 max-w-[1200px] mx-auto flex flex-col gap-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl text-ink-900">Aging report</h1>
            <p className="text-sm text-ink-600 mt-1">Unpaid invoices, grouped by how late they are. Tap a group to see just those.</p>
          </div>
          <button
            onClick={handleExport}
            disabled={exporting || !report || report.total_count === 0}
            className="inline-flex items-center gap-2 rounded-full bg-dx border border-white/[0.08] px-4 py-2 text-sm text-ink-900 hover:border-lime/40 disabled:opacity-40 transition-colors"
          >
            <Download className="w-4 h-4" strokeWidth={2} />
            {exporting ? 'Preparing…' : 'Export CSV'}
          </button>
        </div>

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {!report && !error ? (
          <ListSkeleton rows={5} />
        ) : report ? (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
              {report.buckets.map((b) => {
                const selected = bucket === b.key;
                return (
                  <button
                    key={b.key}
                    onClick={() => setBucket(selected ? null : b.key)}
                    aria-pressed={selected}
                    className={`relative overflow-hidden text-left bg-dx rounded-2xl border p-4 transition-colors ${
                      selected ? 'border-lime/70 ring-1 ring-lime/40' : 'border-white/[0.06] hover:border-white/20'
                    }`}
                  >
                    <span className={`absolute left-0 top-0 bottom-0 w-1 ${TONE[b.key].bar}`} aria-hidden="true" />
                    <p className="text-xs text-ink-600">{b.label}</p>
                    <p className="figure text-lg sm:text-xl text-ink-900 mt-2 whitespace-nowrap">{formatKpi(Number(b.amount))}</p>
                    <p className="text-xs text-ink-400 mt-1">{pluralize(b.count, 'invoice')}</p>
                  </button>
                );
              })}
            </div>

            {total > 0 && (
              <div
                role="img"
                aria-label={report.buckets.map((b) => `${b.label}: ${formatCurrency(Number(b.amount))}`).join(', ')}
                className="flex h-2.5 w-full overflow-hidden rounded-full bg-white/[0.06]"
              >
                {report.buckets
                  .filter((b) => Number(b.amount) > 0)
                  .map((b) => (
                    <span key={b.key} className={TONE[b.key].bar} style={{ width: `${(Number(b.amount) / total) * 100}%` }} />
                  ))}
              </div>
            )}

            <DxCard className="overflow-hidden">
              <div className="flex items-center justify-between px-5 sm:px-6 pt-5 pb-3">
                <h2 className="font-display text-lg text-ink-900">
                  {bucket ? report.buckets.find((b) => b.key === bucket)?.label : 'Worst first'}
                </h2>
                <p className="text-xs text-ink-400">
                  {formatCurrency(total)} owed across {pluralize(report.total_count, 'invoice')}
                </p>
              </div>
              {report.total_count === 0 ? (
                <p className="px-5 sm:px-6 pb-8 pt-2 text-sm text-ink-600">Nothing is owed. Every invoice is paid.</p>
              ) : report.rows.length === 0 ? (
                <p className="px-5 sm:px-6 pb-8 pt-2 text-sm text-ink-600">No invoices in this group.</p>
              ) : (
                <ul className="divide-y divide-white/[0.05] border-t border-white/[0.06]">
                  {report.rows.map((r) => (
                    <li key={r.invoice_id} className="grid grid-cols-[1fr_auto] sm:grid-cols-[1fr_130px_110px_130px] items-center gap-3 px-5 sm:px-6 py-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <Avatar name={r.student_name} size={36} />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-ink-900 truncate">{r.student_name}</p>
                          <p className="text-xs text-ink-400 truncate">
                            {[r.class_name, r.term_name].filter(Boolean).join(' · ') || r.admission_number}
                          </p>
                        </div>
                      </div>
                      <span className="hidden sm:block text-xs text-ink-600">{new Date(r.due_date).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                      <span className={`hidden sm:inline-flex justify-center text-xs font-medium px-2.5 py-1 rounded-full ${TONE[r.bucket].pill}`}>
                        {r.days_overdue > 0 ? `${r.days_overdue} days late` : 'Not yet due'}
                      </span>
                      <span className="figure text-sm text-ink-900 text-right">{formatCurrency(Number(r.balance))}</span>
                    </li>
                  ))}
                </ul>
              )}
              {report.truncated && (
                <p className="px-5 sm:px-6 py-3 text-xs text-ink-400 border-t border-white/[0.06]">Showing the worst {report.rows.length}. Export the CSV for the full list.</p>
              )}
            </DxCard>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
