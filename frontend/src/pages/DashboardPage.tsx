import { useState } from 'react';
import { ChevronDown, ShieldAlert, Users } from 'lucide-react';
import { ListSkeleton } from '../components/ui/Skeleton';
import { AppShell } from '../components/AppShell';
import { StatusBadge } from '../components/ui/StatusBadge';
import { UnallocatedPaymentsCard } from '../components/UnallocatedPaymentsCard';
import { AreaTrendCard } from '../components/dx/AreaTrendCard';
import { BalancesTable } from '../components/dx/BalancesTable';
import { DonutCard, type DonutSegment } from '../components/dx/DonutCard';
import { DxCard } from '../components/dx/DxCard';
import { GaugeCard } from '../components/dx/GaugeCard';
import { KpiCard } from '../components/dx/KpiCard';
import { PromoCard } from '../components/dx/PromoCard';
import { AdminRail } from '../components/dx/RightRail';
import { formatCompact, formatCurrency, formatKpi } from '../components/dx/format';
import { useInvoices } from '../hooks/useInvoices';
import { useAnomalies } from '../hooks/useAnomalies';
import { useDashboardAnalytics, type TermCollectionPoint } from '../hooks/useDashboardAnalytics';
import { useAuthStore } from '../store/authStore';

const RECENT_INVOICES_PAGE_SIZE = 10;
const DONUT_COLORS = ['#E8FFA8', '#B8F24B', '#7BC31F', '#3F7A12'];

/**
 * "Current" means the term whose dates contain today — NOT just the last one in the list. Bursars often
 * generate invoices for the next term ahead of time, so the last term can be a future one that has not
 * started collecting. Between terms, the most recently started term is the more useful one to show.
 */
function pickCurrentTerm(terms: TermCollectionPoint[]): TermCollectionPoint | null {
  const now = new Date();
  const containing = terms.find((t) => new Date(t.start_date) <= now && now <= new Date(t.end_date));
  if (containing) return containing;
  const started = terms.filter((t) => new Date(t.start_date) <= now);
  return started.length > 0 ? started[started.length - 1] : (terms[0] ?? null);
}

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

export function DashboardPage() {
  // Only the most recent page of invoices is fetched; every headline number comes from the analytics
  // endpoint's SQL aggregates instead of summing invoices in the browser.
  const { invoices, loading, error } = useInvoices(undefined, undefined, RECENT_INVOICES_PAGE_SIZE);
  const { anomalies } = useAnomalies();
  const { data: analytics, loading: analyticsLoading } = useDashboardAnalytics();
  const user = useAuthStore((s) => s.user);
  const [pickedTermId, setPickedTermId] = useState<string | null>(null);

  const terms = analytics?.collection_by_term ?? [];
  const selectedTerm = terms.find((t) => t.term_id === pickedTermId) ?? pickCurrentTerm(terms);
  const termBilled = selectedTerm ? Number(selectedTerm.total_billed) : 0;
  const termPaid = selectedTerm ? Number(selectedTerm.total_paid) : 0;
  const termPaidPct = termBilled > 0 ? Math.min(100, Math.round((termPaid / termBilled) * 100)) : 0;

  // An honest comparison with the term before the selected one. A term that has not collected anything yet
  // is "not started", not "-100%", so no delta is shown until both terms have real payments.
  let paidTrend: string | undefined;
  let paidDirection: 'up' | 'down' | 'neutral' = 'neutral';
  const selectedIdx = selectedTerm ? terms.findIndex((t) => t.term_id === selectedTerm.term_id) : -1;
  if (selectedIdx > 0) {
    const previous = Number(terms[selectedIdx - 1].total_paid);
    if (previous > 0 && termPaid > 0) {
      const pct = Math.round(((termPaid - previous) / previous) * 100);
      paidTrend = `${pct >= 0 ? '+' : ''}${pct}% vs last term`;
      paidDirection = pct >= 0 ? 'up' : 'down';
    }
  }

  const totalCollected = analytics ? Number(analytics.total_collected) : 0;
  const totalBilled = terms.reduce((sum, t) => sum + Number(t.total_billed), 0);
  const overdue = analytics?.overdue_count ?? 0;

  const donutSegments: DonutSegment[] = terms
    .filter((t) => Number(t.total_paid) > 0)
    .slice(-4)
    .map((t, i) => ({ name: t.term_name, value: Number(t.total_paid), color: DONUT_COLORS[i % DONUT_COLORS.length] }));

  const firstName = user?.full_name?.trim().split(/\s+/)[0];

  return (
    <AppShell>
      <div className="px-4 sm:px-6 xl:px-8 pt-5 sm:pt-6 pb-24 grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-8 max-w-[1600px] mx-auto">
        <div className="min-w-0 flex flex-col gap-4">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-1">
            <div>
              <h1 className="font-display text-3xl text-ink-900">Overview</h1>
              <p className="text-sm text-ink-600 mt-1">
                {greeting()}
                {firstName ? `, ${firstName}` : ''}. Here's where your school's fee collection stands.
              </p>
            </div>
            {terms.length > 0 && (
              <label className="relative inline-flex items-center">
                <span className="sr-only">Show figures for term</span>
                <select
                  value={selectedTerm?.term_id ?? ''}
                  onChange={(e) => setPickedTermId(e.target.value)}
                  className="appearance-none rounded-full bg-dx border border-white/[0.08] pl-4 pr-9 py-2 text-sm text-ink-900 focus:outline-none focus:border-lime/50 cursor-pointer"
                >
                  {terms.map((t) => (
                    <option key={t.term_id} value={t.term_id}>
                      {t.term_name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 text-ink-600 absolute right-3 pointer-events-none" strokeWidth={2} />
              </label>
            )}
          </div>

          {(user?.role === 'SCHOOL_ADMIN' || user?.role === 'BURSAR') && <UnallocatedPaymentsCard />}

          {error && (
            <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <KpiCard
              label="Collected"
              value={analytics ? termPaid : undefined}
              format={formatKpi}
              trend={paidTrend ?? (selectedTerm ? selectedTerm.term_name : undefined)}
              direction={paidDirection}
            />
            <KpiCard
              label="Outstanding"
              value={analytics ? Number(analytics.total_outstanding) : undefined}
              format={formatKpi}
              trend={analytics ? (Number(analytics.total_outstanding) > 0 ? 'Needs follow-up' : 'Fully collected') : undefined}
              direction={analytics && Number(analytics.total_outstanding) > 0 ? 'down' : 'up'}
            />
            <GaugeCard
              label="Collection goal"
              percent={termPaidPct}
              loading={analyticsLoading || !analytics}
              note={termBilled > 0 ? `of ${formatCompact(termBilled)}` : 'No invoices yet'}
            />
            <KpiCard
              label="Overdue invoices"
              value={analytics ? overdue : undefined}
              format={(n) => String(Math.round(n))}
              trend={analytics ? (overdue > 0 ? 'Review and remind' : 'All on track') : undefined}
              direction={analytics ? (overdue > 0 ? 'down' : 'up') : 'neutral'}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-7 [&>*]:h-full">
              <DonutCard
                title="Collection overview"
                segments={donutSegments}
                centerValue={formatCompact(totalCollected)}
                centerLabel="collected"
                headlineLabel="Total billed, all terms"
                headlineValue={analytics ? formatCurrency(totalBilled) : '—'}
              />
            </div>
            <div className="lg:col-span-5 grid grid-cols-2 gap-4 content-start">
              <DxCard className="p-4">
                <span className="w-9 h-9 rounded-full bg-lime/15 text-lime flex items-center justify-center">
                  <Users className="w-[18px] h-[18px]" strokeWidth={1.75} />
                </span>
                <p className="text-xs text-ink-600 mt-3">Active students</p>
                <p className="figure text-xl text-ink-900 mt-0.5">{analytics ? analytics.active_student_count : '—'}</p>
              </DxCard>
              <DxCard className="p-4">
                <span className="w-9 h-9 rounded-full bg-lime/15 text-lime flex items-center justify-center figure text-sm font-semibold" aria-hidden="true">
                  Σ
                </span>
                <p className="text-xs text-ink-600 mt-3 truncate">Term billed</p>
                <p className="figure text-xl text-ink-900 mt-0.5">{analytics ? formatCompact(termBilled) : '—'}</p>
              </DxCard>
              <AreaTrendCard
                title="Collections by term"
                headline={analytics ? formatCurrency(totalCollected) : '—'}
                subtitle="Collected across all terms"
                points={terms.map((t) => ({ name: t.term_name, paid: Number(t.total_paid) }))}
              />
            </div>

            <div className="lg:col-span-7 [&>*]:h-full">
              <BalancesTable rows={analytics?.top_risk ?? []} />
            </div>
            <div className="lg:col-span-5 [&>*]:h-full">
              <PromoCard outstanding={analytics ? Number(analytics.total_outstanding) : 0} overdueCount={overdue} />
            </div>
          </div>

          <DxCard className="overflow-hidden">
            <div className="px-5 sm:px-6 py-4 border-b border-white/[0.06]">
              <h2 className="font-display text-lg text-ink-900">Recent invoices</h2>
            </div>
            {loading ? (
              <ListSkeleton rows={5} className="p-5" />
            ) : invoices.length === 0 ? (
              <div className="px-5 py-12 text-center">
                <p className="text-sm text-ink-600">No invoices yet.</p>
                <p className="text-xs text-ink-400 mt-1">Generate invoices for a term to start tracking payments.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-ink-400 text-xs">
                      <th className="px-5 sm:px-6 py-2.5 font-medium">Student</th>
                      <th className="px-3 py-2.5 font-medium">Due date</th>
                      <th className="px-3 py-2.5 font-medium text-right">Total</th>
                      <th className="px-3 py-2.5 font-medium text-right">Paid</th>
                      <th className="px-5 sm:px-6 py-2.5 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.05]">
                    {invoices.map((inv) => (
                      <tr key={inv.id} className="h-12 text-ink-900">
                        <td className="px-5 sm:px-6 whitespace-nowrap">{inv.student_name}</td>
                        <td className="px-3 whitespace-nowrap">{new Date(inv.due_date).toLocaleDateString('en-KE')}</td>
                        <td className="px-3 figure text-right whitespace-nowrap">{formatCurrency(Number(inv.total_amount))}</td>
                        <td className="px-3 figure text-right whitespace-nowrap">{formatCurrency(Number(inv.amount_paid))}</td>
                        <td className="px-5 sm:px-6">
                          <StatusBadge status={inv.status} hasActivePaymentPlan={inv.has_active_payment_plan} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </DxCard>

          {anomalies.length > 0 && (
            <div id="flagged" className="bg-dx border border-coral/30 rounded-2xl overflow-hidden">
              <div className="px-5 sm:px-6 py-4 border-b border-white/[0.06] flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-coral" strokeWidth={2} />
                <h2 className="font-display text-lg text-ink-900">
                  Flagged payments <span className="text-ink-400 font-normal text-sm">({anomalies.length})</span>
                </h2>
              </div>
              <div className="divide-y divide-white/[0.05]">
                {anomalies.slice(0, 5).map((a) => (
                  <div key={a.payment_id} className="px-5 sm:px-6 py-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="figure text-sm font-medium text-ink-900">{formatCurrency(Number(a.amount))}</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${a.severity === 'high' ? 'bg-coral-100 text-coral' : 'bg-amber-100 text-amber'}`}>
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

        <aside className="min-w-0 xl:pt-1">
          <AdminRail overdueCount={overdue} flaggedCount={anomalies.length} />
        </aside>
      </div>
    </AppShell>
  );
}
