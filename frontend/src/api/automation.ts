import { apiClient } from './client';

export interface SweepResult {
  invoices_checked: number;
  reminders_sent: number;
  errors: string[];
}

export async function getAutomationSettings(): Promise<{ enabled: boolean }> {
  const { data } = await apiClient.get<{ enabled: boolean }>('/api/automation/settings');
  return data;
}

export async function updateAutomationSettings(enabled: boolean): Promise<{ enabled: boolean }> {
  const { data } = await apiClient.put<{ enabled: boolean }>('/api/automation/settings', { enabled });
  return data;
}

export async function runAutomationNow(): Promise<SweepResult> {
  const { data } = await apiClient.post<SweepResult>('/api/automation/run-now');
  return data;
}
