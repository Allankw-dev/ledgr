import { useState, Fragment } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { ParentShell } from '../components/ParentShell';
import { StatusBadge } from '../components/ui/StatusBadge';
import { PayWithMpesa } from '../components/PayWithMpesa';
import { DownloadReceiptLink } from '../components/DownloadReceiptLink';
import { DownloadInvoicePdfLink } from '../components/DownloadInvoicePdfLink';
import { DownloadStatementLink } from '../components/DownloadStatementLink';
import { PaymentPlanCard } from '../components/PaymentPlanCard';
import { useMyChildren } from '../hooks/useMyChildren';
import { getMyProfile } from '../api/user';
import { useEffect } from 'react';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

export function ParentInvoicesPage() {
  const { children, loading, error, refetch } = useMyChildren();
  const [searchParams, setSearchParams] = useSearchParams();
  const [expandedInvoices, setExpandedInvoices] = useState<Set<string>>(new Set());
  const [phone, setPhone] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const selectedChildId = searchParams.get('child');

  useEffect(() => {
    getMyProfile().then((profile) => setPhone(profile.phone)).catch(() => {});
  }, []);

  function toggleInvoice(id: string) {
    setExpandedInvoices((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

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

  const visibleChildren = selectedChildId ? children.filter((c) => c.id === selectedChildId) : children;

  return (
    <ParentShell>
      <h1 className="font-display text-2xl text-ink-900 font-medium mb-1">Invoices</h1>
      <p className="text-sm text-ink-600 mb-6">Every invoice, itemized, across your children.</p>

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

      {children.length > 1 && (
        <div className="flex gap-2 mb-5 flex-wrap">
          <button
            onClick={() => setSearchParams({})}
            className={`text-xs font-medium px-3 py-1.5 rounded-full border ${
              !selectedChildId ? 'bg-ink-900 text-paper border-ink-900' : 'border-ink-200 text-ink-600 hover:bg-ink-100'
            }`}
          >
            All children
          </button>
          {children.map((c) => (
            <button
              key={c.id}
              onClick={() => setSearchParams({ child: c.id })}
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
      ) : (
        <div className="flex flex-col gap-6">
          {visibleChildren.map((child) => (
            <div key={child.id} className="bg-white border border-ink-200 rounded-lg overflow-hidden">
              <div className="px-5 py-3 border-b border-ink-200 flex items-center justify-between">
                <h2 className="font-display text-base text-ink-900 font-medium">{child.full_name}</h2>
                <DownloadStatementLink studentId={child.id} />
              </div>

              <div className="ledger-lines overflow-x-auto">
                {child.invoices.length === 0 ? (
                  <p className="px-5 py-6 text-sm text-ink-600">No invoices yet for this term.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-ink-600">
                        <th className="px-5 py-2 font-medium w-6"></th>
                        <th className="px-5 py-2 font-medium">Due date</th>
                        <th className="px-5 py-2 font-medium text-right">Total</th>
                        <th className="px-5 py-2 font-medium text-right">Paid</th>
                        <th className="px-5 py-2 font-medium">Status</th>
                        <th className="px-5 py-2 font-medium">Pay / Receipts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {child.invoices.map((inv) => {
                        const isExpanded = expandedInvoices.has(inv.id);
                        const balance = Number(inv.total_amount) - Number(inv.amount_paid);
                        const isUnpaid = inv.status !== 'PAID' && inv.status !== 'CANCELLED';
                        return (
                          <Fragment key={inv.id}>
                            <tr
                              onClick={() => toggleInvoice(inv.id)}
                              className="text-ink-900 cursor-pointer hover:bg-ink-100/60 align-top"
                            >
                              <td className="pl-5 py-2.5 text-ink-400">
                                {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                              </td>
                              <td className="px-5 py-2.5">{new Date(inv.due_date).toLocaleDateString('en-KE')}</td>
                              <td className="px-5 py-2.5 figure text-right">{formatCurrency(Number(inv.total_amount))}</td>
                              <td className="px-5 py-2.5 figure text-right">{formatCurrency(Number(inv.amount_paid))}</td>
                              <td className="px-5 py-2.5">
                                <StatusBadge status={inv.status} hasActivePaymentPlan={inv.has_active_payment_plan} />
                              </td>
                              <td className="px-5 py-2.5" onClick={(e) => e.stopPropagation()}>
                                <div className="flex flex-col gap-1.5 items-start">
                                  <DownloadInvoicePdfLink invoiceId={inv.id} />
                                  {isUnpaid && balance > 0 && (
                                    <PayWithMpesa invoiceId={inv.id} defaultPhone={phone} onInitiated={handlePaymentInitiated} />
                                  )}
                                  {inv.payments.length === 0 ? (
                                    isUnpaid ? null : <span className="text-xs text-ink-400">—</span>
                                  ) : (
                                    inv.payments.map((p) => <DownloadReceiptLink key={p.id} paymentId={p.id} />)
                                  )}
                                </div>
                              </td>
                            </tr>
                            {isExpanded && (
                              <tr className="bg-ink-100/40">
                                <td colSpan={6} className="px-5 py-3">
                                  {inv.items.length === 0 ? (
                                    <p className="text-xs text-ink-500">No itemized breakdown available.</p>
                                  ) : (
                                    <table className="w-full text-xs">
                                      <tbody>
                                        {inv.items.map((item, i) => (
                                          <tr key={i} className="h-6">
                                            <td className="text-ink-600 pl-5">{item.name}</td>
                                            <td className="text-ink-400">{item.category}</td>
                                            <td className="text-right figure text-ink-900 pr-5">
                                              {formatCurrency(Number(item.amount))}
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  )}
                                  {isUnpaid && balance > 0 && (
                                    <div className="mt-3">
                                      <PaymentPlanCard invoiceId={inv.id} />
                                    </div>
                                  )}
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </ParentShell>
  );
}
