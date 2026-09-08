import { useEffect, useState } from 'react';
import { CalendarClock, CheckCircle2, Circle } from 'lucide-react';
import { Button } from './ui/Button';
import { apiClient } from '../api/client';

interface TrackedInstallment {
  sequence: number;
  amount: string;
  due_date: string;
  paid: boolean;
}

interface TrackedPaymentPlan {
  id: string;
  status: string;
  rationale: string;
  installments: TrackedInstallment[];
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

export function PaymentPlanCard({ invoiceId }: { invoiceId: string }) {
  const [plan, setPlan] = useState<TrackedPaymentPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [requesting, setRequesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refetch() {
    try {
      const { data } = await apiClient.get<TrackedPaymentPlan | null>(`/api/invoices/${invoiceId}/payment-plan/active`);
      setPlan(data);
    } catch {
      // Quietly leave the plan unset — the "Request a plan" option below still works.
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceId]);

  async function handleRequest() {
    setRequesting(true);
    setError(null);
    try {
      const { data } = await apiClient.post<TrackedPaymentPlan>(`/api/invoices/${invoiceId}/payment-plan/accept`);
      setPlan(data);
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Could not set up a payment plan for this invoice.';
      setError(message);
    } finally {
      setRequesting(false);
    }
  }

  if (loading) return null;

  if (!plan || plan.status !== 'ACTIVE') {
    return (
      <div className="flex items-center justify-between gap-3 bg-ink-100/60 rounded-md px-3 py-2.5">
        <p className="text-xs text-ink-600">Need to spread this out? We can suggest an installment schedule.</p>
        <Button
          variant="secondary"
          onClick={handleRequest}
          disabled={requesting}
          className="shrink-0 text-xs px-3 py-1.5 flex items-center gap-1.5"
        >
          <CalendarClock className="w-3.5 h-3.5" /> {requesting ? 'Setting up…' : 'Request a payment plan'}
        </Button>
        {error && <p className="text-xs text-clay-700">{error}</p>}
      </div>
    );
  }

  return (
    <div className="bg-ink-100/60 rounded-md px-3 py-3">
      <p className="text-xs text-ink-600 mb-2">{plan.rationale}</p>
      <div className="flex flex-col gap-1.5">
        {plan.installments.map((inst) => (
          <div key={inst.sequence} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5">
              {inst.paid ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
              ) : (
                <Circle className="w-3.5 h-3.5 text-ink-400" />
              )}
              <span className={inst.paid ? 'text-ink-600 line-through' : 'text-ink-900'}>
                Due {new Date(inst.due_date).toLocaleDateString('en-KE')}
              </span>
            </div>
            <span className="figure text-ink-900">{formatCurrency(Number(inst.amount))}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
