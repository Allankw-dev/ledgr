import { apiClient } from './client';
import type { ParentStudentView } from '../types';

export async function listMyChildren(): Promise<ParentStudentView[]> {
  const { data } = await apiClient.get<ParentStudentView[]>('/api/parent/students');
  return data;
}

export async function requestMpesaPayment(invoiceId: string, phoneNumber: string): Promise<{ checkout_request_id: string; message: string }> {
  // Idempotency-Key: stops a double-tap on "Pay now" (or a retried request)
  // from sending a second M-Pesa prompt to the parent's phone.
  const { data } = await apiClient.post(
    '/api/payments/mpesa/stk-push',
    { invoice_id: invoiceId, phone_number: phoneNumber },
    { headers: { 'Idempotency-Key': crypto.randomUUID() } }
  );
  return data;
}

interface LinkGuardianPayload {
  email: string;
  full_name: string;
  phone?: string;
  relationship_type: string;
  is_primary?: boolean;
}

export interface GuardianResponse {
  id: string;
  user_id: string | null;
  full_name: string;
  email: string;
  phone: string | null;
  relationship_type: string;
  is_primary: boolean;
  status: 'linked' | 'invited';
}

export async function linkGuardian(studentId: string, payload: LinkGuardianPayload): Promise<GuardianResponse> {
  const { data } = await apiClient.post(`/api/students/${studentId}/guardians`, payload);
  return data;
}
