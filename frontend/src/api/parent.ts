import { apiClient } from './client';
import type { ParentStudentView } from '../types';

export async function listMyChildren(): Promise<ParentStudentView[]> {
  const { data } = await apiClient.get<ParentStudentView[]>('/api/parent/students');
  return data;
}

/** Pay toward ONE invoice ({ invoiceId }) or a child's WHOLE balance ({ studentId }) —
 *  the server then applies the money to their oldest open invoice first. */
export interface MpesaPayTarget {
  invoiceId?: string;
  studentId?: string;
}

export async function requestMpesaPayment(
  target: MpesaPayTarget,
  phoneNumber: string,
  amount?: number
): Promise<{ checkout_request_id: string; message: string }> {
  // Idempotency-Key: stops a double-tap on "Pay now" (or a retried request)
  // from sending a second M-Pesa prompt to the parent's phone.
  const { data } = await apiClient.post(
    '/api/payments/mpesa/stk-push',
    {
      ...(target.studentId ? { student_id: target.studentId } : { invoice_id: target.invoiceId }),
      phone_number: phoneNumber,
      ...(amount !== undefined ? { amount } : {}),
    },
    { headers: { 'Idempotency-Key': crypto.randomUUID() } }
  );
  return data;
}

interface LinkGuardianPayload {
  phone: string;
  full_name: string;
  email?: string;
  relationship_type: string;
  is_primary?: boolean;
}

export interface GuardianResponse {
  id: string;
  user_id: string | null;
  full_name: string;
  phone: string | null;
  email: string | null;
  relationship_type: string;
  is_primary: boolean;
  status: 'linked' | 'invited';
}

export async function linkGuardian(studentId: string, payload: LinkGuardianPayload): Promise<GuardianResponse> {
  const { data } = await apiClient.post(`/api/students/${studentId}/guardians`, payload);
  return data;
}
