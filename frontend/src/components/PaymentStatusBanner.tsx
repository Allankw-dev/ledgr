import { CheckCircle2, Smartphone } from 'lucide-react';

/** Shown under the page header while a payment is awaiting confirmation, then when it lands. */
export function PaymentStatusBanner({ polling, received }: { polling: boolean; received: number | null }) {
  if (received !== null) {
    return (
      <div role="status" className="pop-in flex items-center gap-2.5 bg-green/10 text-green ring-1 ring-green/25 rounded-lg px-4 py-3 text-sm mb-6">
        <CheckCircle2 className="w-4 h-4 shrink-0" strokeWidth={2} />
        <span>
          Payment of <span className="figure font-semibold">KES {Math.round(received).toLocaleString('en-KE')}</span> received — your balance has been updated.
        </span>
      </div>
    );
  }
  if (polling) {
    return (
      <div role="status" className="flex items-center gap-2.5 bg-ink-100 text-ink-700 rounded-lg px-4 py-3 text-sm mb-6">
        <Smartphone className="w-4 h-4 shrink-0 animate-pulse" strokeWidth={2} />
        Waiting for payment confirmation from M-Pesa — your balance updates automatically.
      </div>
    );
  }
  return null;
}
