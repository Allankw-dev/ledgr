import { useState } from 'react';
import { Search, CheckCircle2 } from 'lucide-react';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { SelectField } from './ui/SelectField';
import { lookupMpesaTransaction, matchMpesaTransaction, type MpesaTransactionLookup } from '../api/mpesa';
import { getErrorMessage } from '../api/client';
import type { InvoiceListItem } from '../types';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

interface ReconcileMpesaPaymentProps {
  invoices: InvoiceListItem[];
  onMatched: () => void;
  onCancel: () => void;
}

/**
 * Handles the "parent paid the paybill directly, not through the app"
 * case: a bursar has an M-Pesa code from the parent (over the phone, on
 * WhatsApp) but the payment never auto-matched — usually because the
 * parent typed the wrong account reference. Two-step flow: look the code
 * up, then attach it to the right invoice.
 */
export function ReconcileMpesaPayment({ invoices, onMatched, onCancel }: ReconcileMpesaPaymentProps) {
  const [transId, setTransId] = useState('');
  const [looking, setLooking] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [txn, setTxn] = useState<MpesaTransactionLookup | null>(null);

  const [invoiceId, setInvoiceId] = useState('');
  const [matching, setMatching] = useState(false);
  const [matchError, setMatchError] = useState<string | null>(null);
  const [matched, setMatched] = useState(false);

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    setLookupError(null);
    setLooking(true);
    try {
      const result = await lookupMpesaTransaction(transId.trim());
      setTxn(result);
    } catch (err: unknown) {
      setLookupError(getErrorMessage(err));
      setTxn(null);
    } finally {
      setLooking(false);
    }
  }

  async function handleMatch(e: React.FormEvent) {
    e.preventDefault();
    if (!txn || !invoiceId) return;
    setMatchError(null);
    setMatching(true);
    try {
      await matchMpesaTransaction(txn.id, invoiceId);
      setMatched(true);
      onMatched();
    } catch (err: unknown) {
      setMatchError(getErrorMessage(err));
    } finally {
      setMatching(false);
    }
  }

  if (matched) {
    return (
      <div className="flex flex-col items-center gap-3 py-6 text-center">
        <CheckCircle2 className="w-8 h-8 text-emerald-600" />
        <p className="text-sm text-ink-900 font-medium">Payment matched and confirmed.</p>
        <Button variant="secondary" onClick={onCancel}>
          Close
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <form onSubmit={handleLookup} className="flex flex-col gap-3">
        <p className="text-sm text-ink-600">
          Enter the M-Pesa transaction code the parent gave you — usually a 10-character code like{' '}
          <span className="figure">QGH7X8ABCD</span>.
        </p>
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <TextField
              label="M-Pesa code"
              value={transId}
              onChange={(e) => setTransId(e.target.value.toUpperCase())}
              placeholder="e.g. QGH7X8ABCD"
            />
          </div>
          <Button type="submit" variant="secondary" disabled={looking || !transId.trim()} className="mb-0.5 flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5" /> {looking ? 'Looking…' : 'Look up'}
          </Button>
        </div>
        {lookupError && (
          <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
            {lookupError}
          </p>
        )}
      </form>

      {txn && (
        <form onSubmit={handleMatch} className="flex flex-col gap-4 border-t border-ink-200 pt-4">
          <div className="bg-ink-100/60 rounded-md px-4 py-3 text-sm">
            <div className="flex justify-between">
              <span className="text-ink-600">Amount</span>
              <span className="figure font-medium text-ink-900">{formatCurrency(Number(txn.amount))}</span>
            </div>
            {txn.payer_name && (
              <div className="flex justify-between mt-1">
                <span className="text-ink-600">Payer</span>
                <span className="text-ink-900">{txn.payer_name}</span>
              </div>
            )}
            {txn.bill_ref_number && (
              <div className="flex justify-between mt-1">
                <span className="text-ink-600">Reference typed</span>
                <span className="text-ink-900">{txn.bill_ref_number}</span>
              </div>
            )}
          </div>

          <SelectField
            label="Attach to invoice"
            value={invoiceId}
            onChange={(e) => setInvoiceId(e.target.value)}
            placeholder="Select an invoice…"
            options={invoices.map((inv) => ({
              value: inv.id,
              label: `${inv.student_name} — ${formatCurrency(Number(inv.total_amount) - Number(inv.amount_paid))} due`,
            }))}
          />

          {matchError && (
            <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
              {matchError}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={matching || !invoiceId}>
              {matching ? 'Matching…' : 'Confirm payment'}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
