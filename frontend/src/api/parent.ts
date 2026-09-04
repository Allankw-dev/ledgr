import { apiClient } from './client';
import type { ParentStudentView } from '../types';

export async function listMyChildren(): Promise<ParentStudentView[]> {
  const { data } = await apiClient.get<ParentStudentView[]>('/api/parent/students');
  return data;
}

export async function requestMpesaPayment(invoiceId: string, phoneNumber: string): Promise<{ checkout_request_id: string; message: string }> {
  const { data } = await apiClient.post('/api/payments/mpesa/stk-push', {
    invoice_id: invoiceId,
    phone_number: phoneNumber,
  });
  return data;
}

interface LinkGuardianPayload {
  email: string;
  full_name: string;
  password: string;
  relationship_type: string;
  is_primary?: boolean;
}

export async function linkGuardian(studentId: string, payload: LinkGuardianPayload) {
  const { data } = await apiClient.post(`/api/students/${studentId}/guardians`, payload);
  return data;
}
