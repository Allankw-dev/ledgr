import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus, ChevronDown, ChevronRight } from 'lucide-react';
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
import { PaymentPlanCard } from '../components/PaymentPlanCard';
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
  const [polling, setPolling] = useState(false);
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

  // After initiating an M-Pesa payment, the parent needs to see their
  // balance update once they enter their PIN on their phone — that
  // confirmation arrives asynchronously via Safaricom's callback, so we
  // poll for a short window rather than expecting an instant update.
  function handlePaymentInitiated() {
    setPolling(true);
    let attempts = 0;
    const interval = setInterval(() => {
      attempts++;
      refetch();
      if (attempts >= 10) {
        clearInterval(interval);
        setPolling(false);
      }
    }, 4000);
  }

  return (
    <ParentShell>
      <div className="flex items-start justify-between gap-4 mb-1">
        <h1 className="font-display text-2xl text-ink-900 font-medium reveal">
          Welcome{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}
        </h1>
        <button
          onClick={() => navigate('/verify-child')}
          className="shrink-0 flex items-center gap-1.5 text-sm font-medium text-ink-900 hover:underline underline-offset-2"
        >
          <UserPlus className="w-4 h-4" strokeWidth={2} />
          Link another child
        </button>
      </div>
      <p className="text-sm text-ink-600 mb-6 reveal" style={{ '--reveal-delay': '0.08s' } as CSSProperties}>
        Here's the fee status for your children.
      </p>

      <div className="mb-6">
        <UpdatePhoneForm currentPhone={phone} onUpdated={setPhone} />
      </div>

      {error && (
        <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
          {error}
        </div>
      )}

      {polling && (
        <div role="status" className="bg-ink-100 text-ink-700 rounded-md px-4 py-3 text-sm mb-6">
          Waiting for payment confirmation from M-Pesa — this updates automatically.
        </div>
      )}

      {loading ? (
        <p className="text-sm text-ink-600">Loading…</p>
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
            const unpaidInvoice = child.invoices.find(
              (inv) => inv.status !== 'PAID' && inv.status !== 'CANCELLED'
            );
            const totalDue = child.invoices.reduce((sum, inv) => sum + Number(inv.total_amount), 0);
            const totalPaid = child.invoices.reduce((sum, inv) => sum + Number(inv.amount_paid), 0);
            const safeTotal = totalDue > 0 ? totalDue : 0;
            const paidPct = safeTotal === 0 ? 100 : Math.min(100, Math.round((totalPaid / safeTotal) * 100));

            return (
              <div key={child.id}>
                {/* Hero balance card — the one number that matters most for this
                   child, with the M-Pesa CTA right where the eye lands first. */}
                <div className="relative overflow-hidden rounded-2xl border border-ink-200 bg-gradient-to-b from-ink-100 to-panel p-7">
                  <div
                    className="absolute -top-20 -right-20 w-56 h-56 rounded-full pointer-events-none"
                    style={{ background: 'radial-gradient(circle, rgba(57,255,136,0.28) 0%, rgba(57,255,136,0) 70%)' }}
                  />
                  <div className="relative flex items-start justify-between gap-4 mb-5">
                    <div>
                      <p className="text-sm text-ink-600">{child.full_name} · Balance due</p>
                      <p className={`figure text-4xl font-medium mt-1.5 ${balance > 0 ? 'text-ink-900' : 'text-emerald-700'}`}>
                        {formatCurrency(balance)}
                      </p>
                    </div>
                    {balance > 0 && unpaidInvoice ? (
                      <PayWithMpesa
                        invoiceId={unpaidInvoice.id}
                        defaultPhone={phone}
                        onInitiated={handlePaymentInitiated}
                        variant="primary"
                        label="Pay with M-Pesa"
                        className="shrink-0 px-5 py-3 rounded-lg text-sm font-semibold flex items-center gap-2"
                      />
                    ) : (
                      child.invoices.length > 0 && <DownloadStatementLink studentId={child.id} />
                    )}
                  </div>

                  {child.invoices.length > 0 && (
                    <div className="relative">
                      <div className="h-1.5 w-full rounded-full bg-ink-200 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            paidPct >= 100 ? 'bg-gradient-to-r from-emerald-800 to-emerald-700' : 'bg-amber-500'
                          }`}
                          style={{
                            width: `${paidPct}%`,
                            boxShadow: paidPct >= 100 ? '0 0 10px rgba(57,255,136,0.35)' : undefined,
                          }}
                        />
                      </div>
                      <div className="flex justify-between text-xs text-ink-600 mt-2">
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
                              className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left hover:bg-ink-100/60 transition-colors"
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                <span className="text-ink-400 shrink-0">
                                  {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
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
                              <div className="px-5 pb-5 border-t border-ink-200 pt-4" onClick={(e) => e.stopPropagation()}>
                                {inv.items.length > 0 && (
                                  <table className="w-full text-xs mb-3">
                                    <tbody>
                                      {inv.items.map((item, i) => (
                                        <tr key={i} className="h-6">
                                          <td className="text-ink-600">{item.name}</td>
                                          <td className="text-ink-400">{item.category}</td>
                                          <td className="text-right figure text-ink-900">{formatCurrency(Number(item.amount))}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                )}

                                <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                                  <div className="flex items-center gap-3">
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

      {!loading && children.length > 0 && (
        <div className="mt-9">
          <RecentActivityFeed children={children} />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start mt-6">
        <ChatWidget />
        <MessagePanel />
      </div>
    </ParentShell>
  );
}
