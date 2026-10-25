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

export interface MpesaMismatch {
  id: string;
  student_id: string;
  student_name: string;
  admission_number: string;
  expected_amount: string;
  reported_amount: string;
  mpesa_receipt: string | null;
  created_at: string | null;
}

/** M-Pesa payments where Safaricom reported a different amount than the prompt asked for. Nothing is credited yet. */
export async function getMpesaMismatches(): Promise<MpesaMismatch[]> {
  const { data } = await apiClient.get<MpesaMismatch[]>('/api/payments/mpesa-mismatches');
  return data;
}

/** Record the payment at the amount M-Pesa actually reported. */
export async function acceptMpesaMismatch(paymentId: string) {
  const { data } = await apiClient.post(
    `/api/payments/${paymentId}/accept-mpesa-amount`,
    {},
    { headers: { 'Idempotency-Key': crypto.randomUUID() } }
  );
  return data;
}

/** Record nothing; the payment is marked failed with the bursar's reason. */
export async function dismissMpesaMismatch(paymentId: string, reason: string) {
  const { data } = await apiClient.post(
    `/api/payments/${paymentId}/dismiss-mpesa`,
    { reason: reason.trim() },
    { headers: { 'Idempotency-Key': crypto.randomUUID() } }
  );
  return data;
}
