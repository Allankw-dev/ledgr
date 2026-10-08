import { CheckCircle2, Smartphone } from 'lucide-react';

/** Shown under the page header while a payment is awaiting confirmation, then when it lands. */
function joinNames(names: string[]) {
  return names.length <= 1 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

export function PaymentStatusBanner({
  polling,
  received,
  watchingFor,
  receivedFor = [],
}: {
  polling: boolean;
  received: number | null;
  /** Child the pending payment is for (only set when the parent has several children). */
  watchingFor?: string | null;
  /** Children whose balance just went down (only set when the parent has several children). */
  receivedFor?: string[];
}) {
  if (received !== null) {
    return (
      <div role="status" className="pop-in flex items-center gap-2.5 bg-green/10 text-green ring-1 ring-green/25 rounded-lg px-4 py-3 text-sm mb-6">
        <CheckCircle2 className="w-4 h-4 shrink-0" strokeWidth={2} />
        <span>
          Payment of <span className="figure font-semibold">KES {Math.round(received).toLocaleString('en-KE')}</span> received
          {receivedFor.length > 0 && <> for <span className="font-semibold">{joinNames(receivedFor)}</span></>} —{' '}
          {receivedFor.length > 0 ? 'their balance has been updated.' : 'your balance has been updated.'}
        </span>
      </div>
    );
  }
  if (polling) {
    return (
      <div role="status" className="flex items-center gap-2.5 bg-ink-100 text-ink-700 rounded-lg px-4 py-3 text-sm mb-6">
        <Smartphone className="w-4 h-4 shrink-0 animate-pulse" strokeWidth={2} />
        <span>
          Waiting for M-Pesa to confirm {watchingFor ? <>the payment for <span className="font-semibold">{watchingFor}</span></> : 'your payment'} —
          the balance updates automatically.
        </span>
      </div>
    );
  }
  return null;
}
