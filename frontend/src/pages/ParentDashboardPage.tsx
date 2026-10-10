import { ListSkeleton } from '../components/ui/Skeleton';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus, ChevronRight, Users, Wallet, CheckCircle2 } from 'lucide-react';
import { ParentShell } from '../components/ParentShell';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { UpdatePhoneForm } from '../components/UpdatePhoneForm';
import { PayWithMpesa } from '../components/PayWithMpesa';
import { ChatWidget } from '../components/ChatWidget';
import { MessagePanel } from '../components/MessagePanel';
import { DownloadReceiptLink } from '../components/DownloadReceiptLink';
import { DownloadStatementLink } from '../components/DownloadStatementLink';
import { RecentActivityFeed } from '../components/RecentActivityFeed';
import { KpiCard } from '../components/dx/KpiCard';
import { GaugeCard } from '../components/dx/GaugeCard';
import { ParentRail } from '../components/dx/RightRail';
import { formatCompact, formatKpi, pluralize } from '../components/dx/format';
import { PaymentPlanCard } from '../components/PaymentPlanCard';
import { AnimatedAmount } from '../components/AnimatedAmount';
import { WelcomeBanner, type WelcomeChip } from '../components/WelcomeBanner';
import { PaymentStatusBanner } from '../components/PaymentStatusBanner';
import { usePaymentWatch } from '../hooks/usePaymentWatch';
import { useMyChildren } from '../hooks/useMyChildren';
import { useAuthStore } from '../store/authStore';
import { getMyProfile } from '../api/user';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

export function ParentDashboardPage() {
  const navigate = useNavigate();
  const { children, loading, error, refetch } = useMyChildren();
  const user = useAuthStore((s) => s.user);
  const [phone, setPhone] = useState<string | null>(null);
  const { polling, received, watchingFor, receivedFor, watch: handlePaymentInitiated } = usePaymentWatch(children, refetch);
  const [expandedInvoices, setExpandedInvoices] = useState<Set<string>>(new Set());

  function toggleInvoice(id: string) {
    setExpandedInvoices((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  useEffect(() => {
    getMyProfile().then((profile) => setPhone(profile.phone)).catch(() => {});
  }, []);

  const manyChildren = children.length > 1;
  const totalOutstanding = children.reduce((sum, c) => sum + Number(c.balance_due), 0);
  // Across every child, the same way each child's own progress bar is worked out below.
  const allInvoices = children.flatMap((c) => c.invoices);
  const totalBilled = allInvoices.reduce((sum, inv) => sum + Number(inv.total_amount), 0);
  const totalPaidAll = allInvoices.reduce((sum, inv) => sum + Number(inv.amount_paid), 0);
  const overallPaidPct = totalBilled > 0 ? Math.min(100, Math.round((totalPaidAll / totalBilled) * 100)) : 100;
  const unpaidCount = allInvoices.filter((inv) => inv.status !== 'PAID' && inv.status !== 'CANCELLED').length;
  const paymentCount = allInvoices.reduce((sum, inv) => sum + inv.payments.length, 0);
  const welcomeChips: WelcomeChip[] = loading || children.length === 0 ? [] : [
    { icon: Users, label: `${children.length} ${children.length === 1 ? 'child' : 'children'} linked` },
    totalOutstanding > 0
      ? { icon: Wallet, label: `${formatCurrency(totalOutstanding)} outstanding`, tone: 'warn' }
      : { icon: CheckCircle2, label: 'All paid up', tone: 'good' },
  ];

  return (
    <ParentShell wide>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_300px] gap-8 items-start">
      <div className="min-w-0">
      <WelcomeBanner
        fullName={user?.full_name}
        role="Parent"
        subtitle="Here's the fee status for your children."
        chips={welcomeChips}
        action={
          <button
            onClick={() => navigate('/verify-child')}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-full bg-white/[0.07] ring-1 ring-white/15 px-3.5 py-2 text-sm font-medium text-ink-900 hover:bg-white/[0.12] transition-colors"
          >
            <UserPlus className="w-4 h-4" strokeWidth={2} />
            Link another child
          </button>
        }
      />

      <div className="mb-6">
        <UpdatePhoneForm currentPhone={phone} onUpdated={setPhone} />
      </div>

      {error && (
        <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
          {error}
        </div>
      )}

      <PaymentStatusBanner polling={polling} received={received} watchingFor={watchingFor} receivedFor={receivedFor} />

      {/* Hidden on phones: the welcome banner already shows the outstanding total there, and the pay button
           for each child should stay on the first screen. */}
      {!loading && children.length > 0 && (
        <div className="hidden md:grid grid-cols-3 gap-4 mb-8">
          <KpiCard
            label="Outstanding"
            value={totalOutstanding}
            format={formatKpi}
            trend={unpaidCount > 0 ? `${pluralize(unpaidCount, 'invoice')} unpaid` : 'All paid up'}
            direction={totalOutstanding > 0 ? 'down' : 'up'}
          />
          <KpiCard
            label="Paid so far"
            value={totalPaidAll}
            format={formatKpi}
            trend={paymentCount > 0 ? pluralize(paymentCount, 'payment') : undefined}
            direction="up"
          />
          <GaugeCard label="Fees paid" percent={overallPaidPct} note={totalBilled > 0 ? `of ${formatCompact(totalBilled)}` : undefined} />
        </div>
      )}

      {loading ? (
        <ListSkeleton rows={3} />
      ) : children.length === 0 ? (
        <div className="bg-panel border border-ink-200 rounded-lg px-6 py-12 text-center">
          <p className="text-sm text-ink-900 font-medium">No children linked to your account yet</p>
          <p className="text-xs text-ink-600 mt-1 mb-4">
            Enter your child's admission number to send a link request to the school office.
          </p>
          <Button onClick={() => navigate('/verify-child')} className="inline-flex items-center gap-2">
            <UserPlus className="w-4 h-4" /> Link a child
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-9">
          {children.map((child) => {
            const balance = Number(child.balance_due);
            // What can actually be collected right now: the same invoices the server
            // counts (issued / part-paid / overdue), so the amount the parent is shown
            // is never more than the server will accept.
            const payable = child.invoices
              .filter((inv) => inv.status === 'ISSUED' || inv.status === 'PARTIALLY_PAID' || inv.status === 'OVERDUE')
              .reduce((sum, inv) => sum + Math.max(Number(inv.total_amount) - Number(inv.amount_paid), 0), 0);
            const totalDue = child.invoices.reduce((sum, inv) => sum + Number(inv.total_amount), 0);
            const totalPaid = child.invoices.reduce((sum, inv) => sum + Number(inv.amount_paid), 0);
            const safeTotal = totalDue > 0 ? totalDue : 0;
            const paidPct = safeTotal === 0 ? 100 : Math.min(100, Math.round((totalPaid / safeTotal) * 100));

            return (
              <div key={child.id}>
                {/* Hero balance card — the one number that matters most for this
                   child, with the M-Pesa CTA right where the eye lands first. */}
                <div className="sheen relative overflow-hidden rounded-2xl border border-ink-200 bg-gradient-to-b from-ink-100 to-panel p-5 sm:p-7 shadow-[0_20px_50px_-24px_rgba(57,255,136,0.35)]">
                  <div
                    className="absolute -top-20 -right-20 w-56 h-56 rounded-full pointer-events-none"
                    style={{ background: 'radial-gradient(circle, rgba(57,255,136,0.28) 0%, rgba(57,255,136,0) 70%)' }}
                  />
                  <div className="relative flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-5">
                    <div>
                      <p className="text-sm text-ink-600">{child.full_name} · Balance due</p>
                      <p className={`figure text-3xl sm:text-4xl font-medium mt-1.5 ${balance > 0 ? 'text-ink-900' : 'text-emerald-700'}`}>
                        <AnimatedAmount value={balance} format={formatCurrency} />
                      </p>
                    </div>
                    {payable >= 1 ? (
                      <PayWithMpesa
                        studentId={child.id}
                        childName={manyChildren ? child.full_name : undefined}
                        detail="Whole outstanding balance · oldest invoice paid first"
                        balance={payable}
                        defaultPhone={phone}
                        onInitiated={handlePaymentInitiated}
                        variant="primary"
                        label={manyChildren ? `Pay for ${child.full_name.trim().split(/\s+/)[0]} with M-Pesa` : 'Pay with M-Pesa'}
                        className="w-full sm:w-auto shrink-0 justify-center px-5 py-3.5 sm:py-3 rounded-lg text-sm font-semibold flex items-center gap-2"
                      />
                    ) : (
                      child.invoices.length > 0 && <DownloadStatementLink studentId={child.id} />
                    )}
                  </div>

                  {child.invoices.length > 0 && (
                    <div className="relative">
                      <div className="h-1.5 w-full rounded-full bg-ink-200 overflow-hidden">
                        <div
                          className={`bar-grow h-full rounded-full transition-all ${
                            paidPct >= 100 ? 'bg-gradient-to-r from-emerald-800 to-emerald-700' : 'bg-amber-500'
                          }`}
                          style={{
                            width: `${paidPct}%`,
                            boxShadow: paidPct >= 100 ? '0 0 10px rgba(57,255,136,0.35)' : undefined,
                          }}
                        />
                      </div>
                      <div className="flex flex-wrap justify-between gap-x-3 gap-y-1 text-xs text-ink-600 mt-2">
                        <span>{child.class_name || 'Class not assigned'}</span>
                        <span className="figure">
                          {formatCurrency(totalPaid)} of {formatCurrency(safeTotal)} paid
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Invoices — simple rows, expandable for the itemized
                   breakdown, receipts, and a payment plan offer. */}
                {child.invoices.length > 0 && (
                  <div className="mt-5">
                    <p className="text-sm text-ink-600 mb-3">Invoices</p>
                    <div className="flex flex-col gap-2.5">
                      {child.invoices.map((inv) => {
                        const isExpanded = expandedInvoices.has(inv.id);
                        const invBalance = Number(inv.total_amount) - Number(inv.amount_paid);
                        const invUnpaid = inv.status !== 'PAID' && inv.status !== 'CANCELLED';
                        const itemSummary = inv.items.map((i) => i.name).join(', ') || 'Fee invoice';

                        return (
                          <div key={inv.id} className="bg-panel border border-ink-200 rounded-xl overflow-hidden">
                            <button
                              onClick={() => toggleInvoice(inv.id)}
                              className="w-full flex items-center justify-between gap-3 px-4 sm:px-5 py-3.5 sm:py-4 text-left hover:bg-ink-100/60 transition-colors"
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                <span className="text-ink-400 shrink-0">
                                  <ChevronRight className={`w-4 h-4 transition-transform duration-300 ${isExpanded ? 'rotate-90' : ''}`} />
                                </span>
                                <div className="min-w-0">
                                  <p className="text-sm font-medium text-ink-900">
                                    Due {new Date(inv.due_date).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' })}
                                  </p>
                                  <p className="text-xs text-ink-600 truncate">{itemSummary}</p>
                                </div>
                              </div>
                              <div className="flex flex-col items-end gap-1.5 shrink-0">
                                <span className="figure text-sm text-ink-900">{formatCurrency(Number(inv.total_amount))}</span>
                                <StatusBadge status={inv.status} hasActivePaymentPlan={inv.has_active_payment_plan} />
                              </div>
                            </button>

                            {isExpanded && (
                              <div className="expand-in px-4 sm:px-5 pb-4 sm:pb-5 border-t border-ink-200 pt-4" onClick={(e) => e.stopPropagation()}>
                                {inv.items.length > 0 && (
                                  <table className="w-full text-xs mb-3 table-fixed">
                                    <tbody>
                                      {inv.items.map((item, i) => (
                                        <tr key={i} className="h-6">
                                          <td className="text-ink-600 pr-2 break-words">{item.name}</td>
                                          <td className="text-ink-400 pr-2 hidden sm:table-cell">{item.category}</td>
                                          <td className="text-right figure text-ink-900 whitespace-nowrap w-24">{formatCurrency(Number(item.amount))}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                )}

                                <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                                    <DownloadStatementLink studentId={child.id} />
                                    {inv.payments.length === 0 ? (
                                      <span className="text-xs text-ink-400">No receipts yet</span>
                                    ) : (
                                      inv.payments.map((p) => <DownloadReceiptLink key={p.id} paymentId={p.id} />)
                                    )}
                                  </div>
                                  {invUnpaid && invBalance > 0 && (
                                    <PayWithMpesa
                                      invoiceId={inv.id}
                                      childName={manyChildren ? child.full_name : undefined}
                                      detail={`Invoice due ${new Date(inv.due_date).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' })}`}
                                      balance={invBalance}
                                      defaultPhone={phone}
                                      onInitiated={handlePaymentInitiated}
                                      variant="secondary"
                                    />
                                  )}
                                </div>

                                {invUnpaid && invBalance > 0 && <PaymentPlanCard invoiceId={inv.id} />}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start mt-6">
        <ChatWidget />
        <MessagePanel />
      </div>
      </div>

      <aside className="min-w-0 xl:pt-2">
        <ParentRail activity={!loading && children.length > 0 ? <RecentActivityFeed variant="rail" children={children} limit={4} /> : null} />
      </aside>
      </div>
    </ParentShell>
  );
}
