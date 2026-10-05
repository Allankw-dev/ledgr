import { useState } from 'react';
import { Smartphone } from 'lucide-react';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { Modal } from './ui/Modal';
import { requestMpesaPayment } from '../api/parent';
import { getErrorMessage } from '../api/client';

// Mirrors the server's rule: part-payments below this aren't sent to M-Pesa
// (paying off whatever is left is always allowed).
const MIN_PART_PAYMENT = 10;

function kes(n: number) {
  return `KES ${Math.round(n).toLocaleString('en-KE')}`;
}

interface PayWithMpesaProps {
  invoiceId: string;
  /** What is still owed on this invoice. When given, the parent types in how much to pay now. */
  balance?: number;
  defaultPhone?: string | null;
  onInitiated: () => void;
  variant?: 'primary' | 'secondary';
  className?: string;
  label?: string;
}

export function PayWithMpesa({ invoiceId, balance, defaultPhone, onInitiated, variant = 'primary', className, label = 'Pay now' }: PayWithMpesaProps) {
  const [open, setOpen] = useState(false);
  const [phone, setPhone] = useState(defaultPhone || '');
  const wholeBalance = balance !== undefined ? Math.floor(balance) : undefined;
  const [amountStr, setAmountStr] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentAmount, setSentAmount] = useState<number | null>(null);
  const [sent, setSent] = useState(false);

  const choosing = wholeBalance !== undefined;
  const amount = amountStr === '' ? NaN : Number(amountStr);

  let amountError: string | null = null;
  if (choosing) {
    if (!Number.isFinite(amount) || amount <= 0) amountError = 'Enter how much you want to pay.';
    else if (!Number.isInteger(amount)) amountError = 'Enter a whole number of shillings.';
    else if (amount > wholeBalance!) amountError = `That is more than the ${kes(wholeBalance!)} still owed.`;
    else if (amount < MIN_PART_PAYMENT && amount !== wholeBalance) amountError = `The smallest part-payment is ${kes(MIN_PART_PAYMENT)}.`;
  }
  const remainingAfter = choosing && !amountError ? wholeBalance! - amount : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (amountError) return;
    setError(null);
    setSubmitting(true);
    try {
      await requestMpesaPayment(invoiceId, phone, choosing ? amount : undefined);
      setSentAmount(choosing ? amount : null);
      setSent(true);
      onInitiated();
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not start the M-Pesa payment. Try again.'));
    } finally {
      setSubmitting(false);
    }
  }

  function openModal() {
    // Always start with an empty box — the parent decides the amount.
    setAmountStr('');
    setOpen(true);
  }

  function close() {
    setOpen(false);
    setSent(false);
    setSentAmount(null);
    setError(null);
  }

  return (
    <>
      <Button
        variant={variant}
        onClick={openModal}
        className={className || 'text-xs px-3.5 py-2 sm:px-3 sm:py-1.5 flex items-center gap-1.5 whitespace-nowrap'}
      >
        <Smartphone className="w-3.5 h-3.5" /> {label}
      </Button>

      {open && (
        <Modal title="Pay with M-Pesa" onClose={close}>
          {!sent ? (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              {choosing && (
                <div className="flex flex-col gap-3">
                  <div className="flex items-baseline justify-between rounded-lg bg-ink-100/70 ring-1 ring-white/5 px-3.5 py-2.5">
                    <span className="text-xs text-ink-600">Still owed on this invoice</span>
                    <span className="figure text-sm font-medium text-ink-900">{kes(wholeBalance!)}</span>
                  </div>

                  <div>
                    <p className="text-sm font-medium text-ink-700">How much would you like to pay now?</p>
                    <p className="text-xs text-ink-600 mt-0.5 mb-2.5">Pay any amount you're comfortable with — you can pay the rest later.</p>
                    <div className="relative">
                      <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-medium text-ink-400">KES</span>
                      <input
                        autoFocus
                        aria-label="Amount to pay in shillings"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        value={amountStr}
                        onChange={(e) => setAmountStr(e.target.value.replace(/[^0-9]/g, ''))}
                        placeholder="Enter an amount"
                        className={`neu-input figure w-full pl-14 pr-3.5 py-3 rounded-md border bg-panel text-ink-900 text-lg font-medium placeholder:text-ink-400 placeholder:text-sm placeholder:font-normal focus-visible:outline-2 focus-visible:outline-ink-600 ${
                          amountError && amountStr !== '' ? 'neu-input-error' : ''
                        }`}
                      />
                    </div>
                    {amountError && amountStr !== '' ? (
                      <p className="text-xs text-clay-700 mt-1.5">{amountError}</p>
                    ) : remainingAfter !== null ? (
                      <p className="text-xs text-ink-600 mt-1.5">
                        {remainingAfter === 0 ? 'This clears the invoice.' : <>Left to pay afterwards: <span className="figure text-ink-900">{kes(remainingAfter)}</span></>}
                      </p>
                    ) : null}
                  </div>
                </div>
              )}

              <p className="text-sm text-ink-600">
                We'll send a payment prompt to this phone. Enter your M-Pesa PIN there to complete it.
              </p>
              <TextField
                label="M-Pesa phone number"
                type="tel"
                placeholder="e.g. 0712345678"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                autoFocus={!choosing}
              />
              {error && <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">{error}</p>}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={close}>
                  Cancel
                </Button>
                <Button type="submit" disabled={submitting || !phone || !!amountError}>
                  {submitting ? 'Sending…' : choosing && !amountError ? `Pay ${kes(amount)}` : 'Send payment request'}
                </Button>
              </div>
            </form>
          ) : (
            <div className="text-center py-4">
              <Smartphone className="w-8 h-8 text-emerald-700 mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-sm text-ink-900 font-medium mb-1">Check your phone</p>
              <p className="text-sm text-ink-600 mb-4">
                A prompt{sentAmount !== null ? <> for <span className="figure text-ink-900">{kes(sentAmount)}</span></> : ''} has been sent to {phone}. Enter your M-Pesa PIN to
                complete the payment — this page will update automatically once it's confirmed.
              </p>
              <Button variant="secondary" onClick={close}>
                Done
              </Button>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
