import { apiClient } from './client';
import type { Page } from '../types';

export interface AuditLogEntry {
  id: string;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export async function listAuditLogs(page = 1, pageSize = 25, action?: string): Promise<Page<AuditLogEntry>> {
  const { data } = await apiClient.get<Page<AuditLogEntry>>('/api/audit-logs', {
    params: { page, page_size: pageSize, action },
  });
  return data;
}

export async function listAuditActions(): Promise<string[]> {
  const { data } = await apiClient.get<string[]>('/api/audit-logs/actions');
  return data;
}
