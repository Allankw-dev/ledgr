import { apiClient } from './client';
import type { ClassGroupSummary, ClassGroupMessage } from '../types';

export async function listClassGroups(): Promise<ClassGroupSummary[]> {
  const { data } = await apiClient.get<ClassGroupSummary[]>('/api/class-groups');
  return data;
}

export async function listClassGroupMessages(classId: string): Promise<ClassGroupMessage[]> {
  const { data } = await apiClient.get<ClassGroupMessage[]>(`/api/class-groups/${classId}/messages`);
  return data;
}

export async function sendClassGroupMessage(classId: string, body: string): Promise<ClassGroupMessage> {
  const { data } = await apiClient.post<ClassGroupMessage>(`/api/class-groups/${classId}/messages`, { body });
  return data;
}
