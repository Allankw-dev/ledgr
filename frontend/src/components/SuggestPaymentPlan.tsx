import { useState } from 'react';
import { CalendarClock } from 'lucide-react';
import { Modal } from './ui/Modal';
import { apiClient } from '../api/client';

interface Installment {
  amount: string;
  due_date: string;
}

interface PaymentPlan {
  installments: Installment[];
  rationale: string;
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

export function SuggestPaymentPlan({ invoiceId }: { invoiceId: string }) {
  const [open, setOpen] = useState(false);
  const [plan, setPlan] = useState<PaymentPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function openAndLoad() {
    setOpen(true);
    if (plan) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<PaymentPlan>(`/api/invoices/${invoiceId}/payment-plan`);
      setPlan(data);
    } catch {
      setError('Could not generate a payment plan for this invoice.');
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
        <CalendarClock className="w-3.5 h-3.5" /> Suggest plan
      </button>

      {open && (
        <Modal title="Suggested payment plan" onClose={() => setOpen(false)}>
          {loading && <p className="text-sm text-ink-600">Working it out…</p>}
          {error && <p className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">{error}</p>}
          {plan && (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-ink-600">{plan.rationale}</p>
              {plan.installments.length === 0 ? (
                <p className="text-sm text-ink-900">Nothing to plan — this invoice is already settled.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-ink-600 border-b border-ink-100">
                      <th className="py-1.5 font-medium">#</th>
                      <th className="py-1.5 font-medium">Due date</th>
                      <th className="py-1.5 font-medium text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.installments.map((inst, i) => (
                      <tr key={i} className="border-b border-ink-100 last:border-0">
                        <td className="py-1.5 text-ink-600">{i + 1}</td>
                        <td className="py-1.5">{new Date(inst.due_date).toLocaleDateString('en-KE')}</td>
                        <td className="py-1.5 figure text-right">{formatCurrency(Number(inst.amount))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="text-xs text-ink-400">
                This is a suggestion for discussing a plan with the family — it doesn't change the invoice or
                schedule anything automatically.
              </p>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
