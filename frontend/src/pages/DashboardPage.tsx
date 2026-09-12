import type { CSSProperties } from 'react';
import { Wallet, AlertCircle, Users, Receipt, ShieldAlert, TrendingUp } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { StatCard } from '../components/ui/StatCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { CollectionChart } from '../components/CollectionChart';
import { TopRiskList } from '../components/TopRiskList';
import { useInvoices } from '../hooks/useInvoices';
import { useAnomalies } from '../hooks/useAnomalies';
import { useDashboardAnalytics } from '../hooks/useDashboardAnalytics';
import { useAuthStore } from '../store/authStore';

function formatCurrency(amount: number, currency = 'KES') {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
}

const RECENT_INVOICES_PAGE_SIZE = 10;

export function DashboardPage() {
  // Only the most recent page is fetched here — the headline numbers below
  // come from the analytics endpoint's SQL aggregates instead of summing
  // every invoice client-side, which is what made this page slow to load
  // as the number of students and invoices grew.
  const { invoices, loading, error } = useInvoices(undefined, undefined, RECENT_INVOICES_PAGE_SIZE);
  const { anomalies } = useAnomalies();
  const { data: analytics } = useDashboardAnalytics();
  const user = useAuthStore((s) => s.user);

  const recentInvoices = invoices;

  // A real, honest comparison — not a fabricated "this week" delta the
  // backend has no data for. collection_by_term is ordered chronologically,
  // so the last two entries are the current and previous term.
  let collectedTrend: string | undefined;
  let collectedTrendDirection: 'up' | 'down' | 'neutral' = 'neutral';
  if (analytics && analytics.collection_by_term.length >= 2) {
    const terms = analytics.collection_by_term;
    const current = Number(terms[terms.length - 1].total_paid);
    const previous = Number(terms[terms.length - 2].total_paid);
    // Only compare once the current term has actually collected something.
    // A brand-new term starts at zero by definition — that's not a "-100%"
    // decline, it just hasn't begun yet, so showing a delta there would be
    // a false alarm rather than a real signal.
    if (previous > 0 && current > 0) {
      const pctChange = ((current - previous) / previous) * 100;
      const rounded = Math.round(pctChange);
      collectedTrend = `${rounded >= 0 ? '+' : ''}${rounded}% vs last term`;
      collectedTrendDirection = rounded >= 0 ? 'up' : 'down';
    }
  }

  // For the "Term collection" progress panel — the current term's own
  // billed/paid totals, so the percentage reflects this term specifically
  // rather than the all-time total_collected figure used in the hero stat.
  const currentTermPoint =
    analytics && analytics.collection_by_term.length > 0
      ? analytics.collection_by_term[analytics.collection_by_term.length - 1]
      : null;
  const termBilled = currentTermPoint ? Number(currentTermPoint.total_billed) : 0;
  const termPaid = currentTermPoint ? Number(currentTermPoint.total_paid) : 0;
  const termPaidPct = termBilled > 0 ? Math.min(100, Math.round((termPaid / termBilled) * 100)) : 0;

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <div className="mb-8">
          <h1 className="font-display text-2xl text-ink-900 font-medium reveal">
            Good day{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}
          </h1>
          <p className="text-sm text-ink-600 mt-1 reveal" style={{ '--reveal-delay': '0.08s' } as CSSProperties}>
            Here's where your school's fee collection stands.
          </p>
        </div>

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Collected this term"
            value={!analytics ? '—' : formatCurrency(Number(analytics.total_collected))}
            trend={collectedTrend}
            trendDirection={collectedTrendDirection}
            icon={<Wallet className="w-5 h-5" strokeWidth={1.75} />}
            highlight
          />
          <StatCard
            label="Outstanding balance"
            value={!analytics ? '—' : formatCurrency(Number(analytics.total_outstanding))}
            trend={!!analytics && Number(analytics.total_outstanding) > 0 ? 'Needs follow-up' : undefined}
            trendDirection="down"
            icon={<Receipt className="w-5 h-5" strokeWidth={1.75} />}
          />
          <StatCard
            label="Overdue invoices"
            value={!analytics ? '—' : String(analytics.overdue_count)}
            trend={!!analytics && analytics.overdue_count > 0 ? 'Review and remind' : 'All on track'}
            trendDirection={!!analytics && analytics.overdue_count > 0 ? 'down' : 'up'}
            icon={<AlertCircle className="w-5 h-5" strokeWidth={1.75} />}
          />
          <StatCard
            label="Active students"
            value={!analytics ? '—' : String(analytics.active_student_count)}
            icon={<Users className="w-5 h-5" strokeWidth={1.75} />}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.55fr_1fr] gap-4 mb-8 items-start">
            <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden">
              <div className="px-5 py-4 border-b border-ink-200 flex items-center justify-between">
                <h2 className="font-display text-base text-ink-900 font-medium">Recent invoices</h2>
              </div>

              {loading ? (
                <div className="px-5 py-12 text-center text-sm text-ink-600">Loading invoices…</div>
              ) : recentInvoices.length === 0 ? (
                <div className="px-5 py-12 text-center">
                  <p className="text-sm text-ink-600">No invoices yet.</p>
                  <p className="text-xs text-ink-400 mt-1">
                    Generate invoices for a term to start tracking payments.
                  </p>
                </div>
              ) : (
                <div className="ledger-lines overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-ink-600">
                        <th className="px-5 py-2 font-medium">Student</th>
                        <th className="px-5 py-2 font-medium">Due date</th>
                        <th className="px-5 py-2 font-medium text-right">Total</th>
                        <th className="px-5 py-2 font-medium text-right">Paid</th>
                        <th className="px-5 py-2 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentInvoices.map((inv) => (
                        <tr key={inv.id} className="h-9 text-ink-900">
                          <td className="px-5">{inv.student_name}</td>
                          <td className="px-5">{new Date(inv.due_date).toLocaleDateString('en-KE')}</td>
                          <td className="px-5 figure text-right">{formatCurrency(Number(inv.total_amount))}</td>
                          <td className="px-5 figure text-right">{formatCurrency(Number(inv.amount_paid))}</td>
                          <td className="px-5">
                            <StatusBadge status={inv.status} hasActivePaymentPlan={inv.has_active_payment_plan} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex flex-col gap-4">
              {currentTermPoint && (
                <div className="bg-panel border border-ink-200 rounded-lg p-5">
                  <h2 className="font-display text-base text-ink-900 font-medium mb-4">Term collection</h2>
                  <div className="h-1.5 w-full rounded-full bg-ink-200 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-emerald-800 to-emerald-700"
                      style={{ width: `${termPaidPct}%`, boxShadow: '0 0 12px rgba(57,255,136,0.35)' }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-ink-600 mt-2.5">
                    <span>{formatCurrency(termPaid)} collected</span>
                    <span className="figure">{termPaidPct}%</span>
                  </div>
                </div>
              )}

              {analytics && analytics.top_risk.length > 0 && (
                <div className="bg-panel border border-ink-200 rounded-lg p-5">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertCircle className="w-4 h-4 text-ink-600" strokeWidth={2} />
                    <h2 className="font-display text-base text-ink-900 font-medium">Highest-risk unpaid invoices</h2>
                  </div>
                  <TopRiskList invoices={analytics.top_risk} />
                </div>
              )}
            </div>
          </div>

        {analytics && analytics.collection_by_term.length > 0 && (
          <div className="bg-panel border border-ink-200 rounded-lg p-5 mb-8">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-4 h-4 text-ink-600" strokeWidth={2} />
              <h2 className="font-display text-base text-ink-900 font-medium">Collection by term</h2>
            </div>
            <CollectionChart points={analytics.collection_by_term} />
          </div>
        )}

        {anomalies.length > 0 && (
          <div className="bg-panel border border-clay-600/30 rounded-lg overflow-hidden mb-8">
            <div className="px-5 py-4 border-b border-ink-200 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-clay-700" strokeWidth={2} />
              <h2 className="font-display text-base text-ink-900 font-medium">
                Flagged payments <span className="text-ink-400 font-normal text-sm">({anomalies.length})</span>
              </h2>
            </div>
            <div className="divide-y divide-ink-100">
              {anomalies.slice(0, 5).map((a) => (
                <div key={a.payment_id} className="px-5 py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="figure text-sm font-medium text-ink-900">
                      {formatCurrency(Number(a.amount))}
                    </span>
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        a.severity === 'high' ? 'bg-clay-100 text-clay-700' : 'bg-amber-100 text-amber-700'
                      }`}
                    >
                      {a.severity === 'high' ? 'Review recommended' : 'Worth a look'}
                    </span>
                  </div>
                  {a.reasons.map((reason, i) => (
                    <p key={i} className="text-xs text-ink-600">
                      {reason}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </AppShell>
  );
}
