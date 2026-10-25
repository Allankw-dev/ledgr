import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import {
  acceptMpesaMismatch,
  dismissMpesaMismatch,
  getMpesaMismatches,
  type MpesaMismatch,
} from '../api/payments';
import { getErrorMessage } from '../api/client';

function kes(amount: number | string) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 2 }).format(Number(amount));
}

function MismatchRow({ item, onResolved }: { item: MpesaMismatch; onResolved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissing, setDismissing] = useState(false);
  const [reason, setReason] = useState('');

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

  const reasonTooShort = reason.trim().length < 3;

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-sm text-ink-900">
          <span className="font-medium">{item.student_name}</span>
          <span className="text-ink-600"> · Adm {item.admission_number}</span>
        </p>
        <p className="text-sm text-ink-900">
          asked <span className="figure">{kes(item.expected_amount)}</span> · M-Pesa says{' '}
          <span className="figure font-medium">{kes(item.reported_amount)}</span>
        </p>
      </div>
      {item.mpesa_receipt && (
        <p className="text-xs text-ink-600 mt-0.5">
          M-Pesa code <span className="figure">{item.mpesa_receipt}</span>
        </p>
      )}

      {error && (
        <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2 mt-3">
          {error}
        </p>
      )}

      {dismissing ? (
        <div className="mt-3 flex flex-col gap-3 sm:max-w-md">
          <p className="text-xs text-ink-600">
            Nothing will be recorded for this payment. Say why, so the audit log shows it.
          </p>
          <TextField label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Safaricom reversed it" />
          <div className="flex gap-2">
            <Button variant="danger" disabled={busy || reasonTooShort} onClick={() => run(() => dismissMpesaMismatch(item.id, reason))}>
              {busy ? 'Saving…' : 'Dismiss payment'}
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => setDismissing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-3">
          <Button disabled={busy} onClick={() => run(() => acceptMpesaMismatch(item.id))}>
            {busy ? 'Recording…' : `Record ${kes(item.reported_amount)}`}
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => setDismissing(true)}>
            Dismiss
          </Button>
        </div>
      )}
    </li>
  );
}

/**
 * Shows only when there is something to decide. When M-Pesa confirms a payment for a different
 * amount than the prompt asked for, Ledgr credits nothing and waits for a person: the parent may
 * have typed over the prompt, or the money may already have been reversed.
 */
export function MpesaMismatchCard() {
  const [items, setItems] = useState<MpesaMismatch[]>([]);

  const load = useCallback(async () => {
    try {
      setItems(await getMpesaMismatches());
    } catch {
      setItems([]); // a failed check must never break the dashboard
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (items.length === 0) return null;

  return (
    <section aria-labelledby="mismatch-title" className="bg-amber-100 border border-amber-200 rounded-lg p-5 mb-6">
      <div className="flex items-start gap-3 mb-4">
        <AlertTriangle className="w-5 h-5 text-amber shrink-0 mt-0.5" aria-hidden />
        <div>
          <h2 id="mismatch-title" className="font-display text-base text-ink-900 font-medium">
            {items.length === 1 ? '1 M-Pesa payment' : `${items.length} M-Pesa payments`} for a different amount than asked
          </h2>
          <p className="text-sm text-ink-600 mt-0.5">
            Nothing has been credited to these students yet. Check the M-Pesa code against your statement, then record or dismiss each one.
          </p>
        </div>
      </div>
      <ul className="divide-y divide-amber-200">
        {items.map((item) => (
          <MismatchRow key={item.id} item={item} onResolved={load} />
        ))}
      </ul>
    </section>
  );
}
