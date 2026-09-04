import { useState } from 'react';
import { Receipt } from 'lucide-react';
import { Modal } from './ui/Modal';
import { DownloadReceiptLink } from './DownloadReceiptLink';
import { apiClient } from '../api/client';

interface Payment {
  id: string;
  amount: string;
  method: string;
  paid_at: string | null;
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

export function ViewPaymentsButton({ invoiceId }: { invoiceId: string }) {
  const [open, setOpen] = useState(false);
  const [payments, setPayments] = useState<Payment[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function openAndLoad() {
    setOpen(true);
    if (payments) return;
    setLoading(true);
    try {
      const { data } = await apiClient.get<Payment[]>(`/api/invoices/${invoiceId}/payments`);
      setPayments(data);
    } catch {
      setPayments([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={openAndLoad}
        className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
      >
        <Receipt className="w-3.5 h-3.5" /> Payments
      </button>

      {open && (
        <Modal title="Payment history" onClose={() => setOpen(false)}>
          {loading && <p className="text-sm text-ink-600">Loading…</p>}
          {payments && payments.length === 0 && (
            <p className="text-sm text-ink-600">No payments recorded on this invoice yet.</p>
          )}
          {payments && payments.length > 0 && (
            <div className="flex flex-col divide-y divide-ink-100">
              {payments.map((p) => (
                <div key={p.id} className="py-3 flex items-center justify-between">
                  <div>
                    <p className="figure text-sm font-medium text-ink-900">{formatCurrency(Number(p.amount))}</p>
                    <p className="text-xs text-ink-600">
                      {p.method.replace('_', ' ')} ·{' '}
                      {p.paid_at ? new Date(p.paid_at).toLocaleDateString('en-KE') : '—'}
                    </p>
                  </div>
                  <DownloadReceiptLink paymentId={p.id} />
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
