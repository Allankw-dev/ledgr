import { apiClient } from './client';

export interface MpesaTransactionLookup {
  id: string;
  trans_id: string;
  trans_time: string | null;
  amount: string;
  bill_ref_number: string | null;
  msisdn: string | null;
  payer_name: string | null;
  status: string;
}

export async function lookupMpesaTransaction(transId: string): Promise<MpesaTransactionLookup> {
  const { data } = await apiClient.get<MpesaTransactionLookup>('/api/payments/mpesa/reconciliation/lookup', {
    params: { trans_id: transId },
  });
  return data;
}

export async function matchMpesaTransaction(
  transactionId: string,
  invoiceId: string
): Promise<{ status: string; matched_payment_id: string | null }> {
  const { data } = await apiClient.post(`/api/payments/mpesa/reconciliation/${transactionId}/match`, {
    invoice_id: invoiceId,
  });
  return data;
}
