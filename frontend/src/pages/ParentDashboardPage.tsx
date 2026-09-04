import { useEffect, useState } from 'react';
import { ParentShell } from '../components/ParentShell';
import { StatusBadge } from '../components/ui/StatusBadge';
import { UpdatePhoneForm } from '../components/UpdatePhoneForm';
import { PayWithMpesa } from '../components/PayWithMpesa';
import { ChatWidget } from '../components/ChatWidget';
import { DownloadReceiptLink } from '../components/DownloadReceiptLink';
import { useMyChildren } from '../hooks/useMyChildren';
import { useAuthStore } from '../store/authStore';
import { getMyProfile } from '../api/user';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

export function ParentDashboardPage() {
  const { children, loading, error, refetch } = useMyChildren();
  const user = useAuthStore((s) => s.user);
  const [phone, setPhone] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

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
      <h1 className="font-display text-2xl text-ink-900 font-medium mb-1">
        Welcome{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}
      </h1>
      <p className="text-sm text-ink-600 mb-6">Here's the fee status for your children.</p>

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
        <div className="bg-white border border-ink-200 rounded-lg px-6 py-12 text-center">
          <p className="text-sm text-ink-900 font-medium">No children linked to your account yet</p>
          <p className="text-xs text-ink-600 mt-1">
            Contact your school's office to have your account linked to your child's record.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {children.map((child) => {
            const balance = Number(child.balance_due);
            const unpaidInvoice = child.invoices.find(
              (inv) => inv.status !== 'PAID' && inv.status !== 'CANCELLED'
            );
            return (
              <div key={child.id} className="bg-white border border-ink-200 rounded-lg overflow-hidden">
                <div className="px-5 py-4 border-b border-ink-200 flex items-start justify-between">
                  <div>
                    <h2 className="font-display text-lg text-ink-900 font-medium">{child.full_name}</h2>
                    <p className="text-xs text-ink-600 mt-0.5">
                      {child.class_name || 'Class not assigned'} · {child.admission_number}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-ink-600">Balance due</p>
                    <p className={`figure text-xl font-medium ${balance > 0 ? 'text-clay-700' : 'text-emerald-700'}`}>
                      {formatCurrency(balance)}
                    </p>
                  </div>
                </div>

                {balance > 0 && unpaidInvoice && (
                  <div className="px-5 py-3 bg-amber-100/40 border-b border-ink-200 flex items-center justify-between">
                    <p className="text-xs text-ink-700">Pay this balance via M-Pesa</p>
                    <PayWithMpesa
                      invoiceId={unpaidInvoice.id}
                      defaultPhone={phone}
                      onInitiated={handlePaymentInitiated}
                    />
                  </div>
                )}

                <div className="ledger-lines">
                  {child.invoices.length === 0 ? (
                    <p className="px-5 py-6 text-sm text-ink-600">No invoices yet for this term.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-ink-600">
                          <th className="px-5 py-2 font-medium">Due date</th>
                          <th className="px-5 py-2 font-medium text-right">Total</th>
                          <th className="px-5 py-2 font-medium text-right">Paid</th>
                          <th className="px-5 py-2 font-medium">Status</th>
                          <th className="px-5 py-2 font-medium">Receipts</th>
                        </tr>
                      </thead>
                      <tbody>
                        {child.invoices.map((inv) => (
                          <tr key={inv.id} className="h-9 text-ink-900">
                            <td className="px-5">{new Date(inv.due_date).toLocaleDateString('en-KE')}</td>
                            <td className="px-5 figure text-right">{formatCurrency(Number(inv.total_amount))}</td>
                            <td className="px-5 figure text-right">{formatCurrency(Number(inv.amount_paid))}</td>
                            <td className="px-5">
                              <StatusBadge status={inv.status} />
                            </td>
                            <td className="px-5">
                              <div className="flex flex-col gap-1">
                                {inv.payments.length === 0 ? (
                                  <span className="text-xs text-ink-400">—</span>
                                ) : (
                                  inv.payments.map((p) => <DownloadReceiptLink key={p.id} paymentId={p.id} />)
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <ChatWidget />
    </ParentShell>
  );
}
