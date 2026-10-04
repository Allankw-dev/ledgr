import { apiClient } from './client';

export interface UnallocatedInvoiceOption {
  id: string;
  label: string;
  due_date: string | null;
  balance: string;
}

export interface UnallocatedPayment {
  id: string;
  student_id: string;
  student_name: string;
  admission_number: string;
  amount: string;
  method: string;
  reference_code: string | null;
  paid_at: string | null;
  notes: string | null;
  open_invoices: UnallocatedInvoiceOption[];
}

/** Confirmed money that has no invoice behind it and needs a bursar's decision. */
export async function getUnallocatedPayments(): Promise<UnallocatedPayment[]> {
  const { data } = await apiClient.get<UnallocatedPayment[]>('/api/payments/unallocated');
  return data;
}

export async function applyUnallocatedPayment(paymentId: string, invoiceId: string) {
  // Idempotency-Key: a double-click must not apply the same money twice.
  const { data } = await apiClient.post(
    `/api/payments/${paymentId}/apply`,
    { invoice_id: invoiceId },
    { headers: { 'Idempotency-Key': crypto.randomUUID() } }
  );
  return data;
}

/** "Refunded" is recorded as a reversal, so the ledger keeps both the receipt and the refund. */
export async function markPaymentRefunded(paymentId: string, note: string) {
  const reason = note.trim() ? `Refunded to payer — ${note.trim()}` : 'Refunded to payer';
  const { data } = await apiClient.post(
    `/api/payments/${paymentId}/reverse`,
    { reason },
    { headers: { 'Idempotency-Key': crypto.randomUUID() } }
  );
  return data;
}
