import { useState } from 'react';
import { Smartphone } from 'lucide-react';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { Modal } from './ui/Modal';
import { requestMpesaPayment } from '../api/parent';

interface PayWithMpesaProps {
  invoiceId: string;
  defaultPhone?: string | null;
  onInitiated: () => void;
  variant?: 'primary' | 'secondary';
  className?: string;
  label?: string;
}

export function PayWithMpesa({ invoiceId, defaultPhone, onInitiated, variant = 'primary', className, label = 'Pay now' }: PayWithMpesaProps) {
  const [open, setOpen] = useState(false);
  const [phone, setPhone] = useState(defaultPhone || '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await requestMpesaPayment(invoiceId, phone);
      setSent(true);
      onInitiated();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
        'Could not start the M-Pesa payment. Try again.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  function close() {
    setOpen(false);
    setSent(false);
    setError(null);
  }

  return (
    <>
      <Button
        variant={variant}
        onClick={() => setOpen(true)}
        className={className || 'text-xs px-3 py-1.5 flex items-center gap-1.5'}
      >
        <Smartphone className="w-3.5 h-3.5" /> {label}
      </Button>

      {open && (
        <Modal title="Pay with M-Pesa" onClose={close}>
          {!sent ? (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
                autoFocus
              />
              {error && <p className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">{error}</p>}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={close}>
                  Cancel
                </Button>
                <Button type="submit" disabled={submitting || !phone}>
                  {submitting ? 'Sending…' : 'Send payment request'}
                </Button>
              </div>
            </form>
          ) : (
            <div className="text-center py-4">
              <Smartphone className="w-8 h-8 text-emerald-700 mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-sm text-ink-900 font-medium mb-1">Check your phone</p>
              <p className="text-sm text-ink-600 mb-4">
                A payment prompt has been sent to {phone}. Enter your M-Pesa PIN to complete the payment — this
                page will update automatically once it's confirmed.
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
