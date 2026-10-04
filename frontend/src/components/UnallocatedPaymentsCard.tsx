import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from './ui/Button';
import { SelectField } from './ui/SelectField';
import { TextField } from './ui/TextField';
import {
  applyUnallocatedPayment,
  getUnallocatedPayments,
  markPaymentRefunded,
  type UnallocatedPayment,
} from '../api/payments';
import { getErrorMessage } from '../api/client';

function kes(amount: number | string) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(Number(amount));
}

function formatDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
}

function PaymentRow({ payment, onResolved }: { payment: UnallocatedPayment; onResolved: () => void }) {
  const [invoiceId, setInvoiceId] = useState(payment.open_invoices[0]?.id ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refunding, setRefunding] = useState(false);
  const [note, setNote] = useState('');

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onResolved();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
      setBusy(false);
    }
  }

  const chosen = payment.open_invoices.find((i) => i.id === invoiceId);
  const amount = Number(payment.amount);

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-sm text-ink-900">
          <span className="font-medium">{payment.student_name}</span>
          <span className="text-ink-600"> · Adm {payment.admission_number}</span>
        </p>
        <p className="figure text-base text-ink-900">{kes(payment.amount)}</p>
      </div>
      <p className="text-xs text-ink-600 mt-0.5">
        {payment.method}
        {payment.reference_code && <> · code <span className="figure">{payment.reference_code}</span></>} · received {formatDate(payment.paid_at)}
      </p>

      {error && (
        <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2 mt-3">
          {error}
        </p>
      )}

      {refunding ? (
        <div className="mt-3 flex flex-col gap-3 sm:max-w-md">
          <p className="text-xs text-ink-600">
            Only do this once you have actually sent {kes(payment.amount)} back to the payer. Ledgr records the refund; it does not send money.
          </p>
          <TextField label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. sent back via M-Pesa 12 Oct" />
          <div className="flex gap-2">
            <Button variant="danger" disabled={busy} onClick={() => run(() => markPaymentRefunded(payment.id, note))}>
              {busy ? 'Saving…' : 'Confirm refund'}
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => setRefunding(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap items-end gap-3">
          {payment.open_invoices.length > 0 ? (
            <>
              <div className="min-w-[14rem] flex-1 sm:flex-none">
                <SelectField
                  label="Apply to"
                  id={`apply-${payment.id}`}
                  value={invoiceId}
                  onChange={(e) => setInvoiceId(e.target.value)}
                  options={payment.open_invoices.map((i) => ({
                    value: i.id,
                    label: `${i.label} · due ${formatDate(i.due_date)} · owes ${kes(i.balance)}`,
                  }))}
                />
              </div>
              <Button disabled={busy || !invoiceId} onClick={() => run(() => applyUnallocatedPayment(payment.id, invoiceId))}>
                {busy ? 'Applying…' : chosen && Number(chosen.balance) < amount ? `Apply ${kes(chosen.balance)}` : 'Apply'}
              </Button>
            </>
          ) : (
            <p className="text-xs text-ink-600 max-w-sm">
              This student has no open invoice right now. Apply it when their next invoice is issued, or refund it.
            </p>
          )}
          <Button variant="secondary" disabled={busy} onClick={() => setRefunding(true)}>
            Mark refunded
          </Button>
        </div>
      )}
    </li>
  );
}

/**
 * Shows only when there is something to decide. An M-Pesa payment that arrives after the
 * student's invoices were already paid has no invoice to sit against: the money is safe
 * in the ledger, but until someone applies it or refunds it, it's easy to forget.
 */
export function UnallocatedPaymentsCard() {
  const [payments, setPayments] = useState<UnallocatedPayment[]>([]);

  const load = useCallback(async () => {
    try {
      setPayments(await getUnallocatedPayments());
    } catch {
      setPayments([]); // a failed check must never break the dashboard
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (payments.length === 0) return null;

  const total = payments.reduce((sum, p) => sum + Number(p.amount), 0);

  return (
    <section aria-labelledby="unallocated-title" className="bg-amber-100 border border-amber-200 rounded-lg p-5 mb-6">
      <div className="flex items-start gap-3 mb-4">
        <AlertTriangle className="w-5 h-5 text-amber shrink-0 mt-0.5" aria-hidden />
        <div>
          <h2 id="unallocated-title" className="font-display text-base text-ink-900 font-medium">
            {payments.length === 1 ? '1 payment' : `${payments.length} payments`} waiting for an invoice · {kes(total)}
          </h2>
          <p className="text-sm text-ink-600 mt-0.5">
            This money was received after the student's invoices were already paid. It's safe in the ledger, but needs your decision.
          </p>
        </div>
      </div>
      <ul className="divide-y divide-amber-200">
        {payments.map((p) => (
          <PaymentRow key={p.id} payment={p} onResolved={load} />
        ))}
      </ul>
    </section>
  );
}
