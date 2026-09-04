import { apiClient } from './client';

export interface StudentLookupResult {
  student_id: string;
  full_name: string;
  class_name: string | null;
  school_name: string;
}

export async function lookupStudent(admissionNumber: string): Promise<StudentLookupResult> {
  const { data } = await apiClient.get<StudentLookupResult>('/api/students/lookup', {
    params: { admission_number: admissionNumber },
  });
  return data;
}

export async function requestLink(studentId: string, relationshipType: string) {
  const { data } = await apiClient.post(`/api/students/${studentId}/request-link`, {
    relationship_type: relationshipType,
  });
  return data;
}

export interface PendingGuardianRequest {
  id: string;
  student_id: string;
  student_name: string;
  parent_name: string;
  parent_email: string;
  relationship_type: string;
  requested_at: string;
}

export async function listPendingRequests(): Promise<PendingGuardianRequest[]> {
  const { data } = await apiClient.get<PendingGuardianRequest[]>('/api/guardian-requests');
  return data;
}

export async function approveRequest(id: string) {
  const { data } = await apiClient.post(`/api/guardian-requests/${id}/approve`);
  return data;
}

export async function rejectRequest(id: string) {
  const { data } = await apiClient.post(`/api/guardian-requests/${id}/reject`);
  return data;
}
