import { apiClient } from './client';

export type AgingBucketKey = 'current' | '1-30' | '31-60' | '61-90' | '90+';

export interface AgingBucket {
  key: AgingBucketKey;
  label: string;
  count: number;
  amount: string;
}

export interface AgingRow {
  invoice_id: string;
  student_id: string;
  student_name: string;
  admission_number: string;
  class_name: string | null;
  term_name: string | null;
  due_date: string;
  days_overdue: number;
  balance: string;
  bucket: AgingBucketKey;
}

export interface AgingReport {
  buckets: AgingBucket[];
  total_count: number;
  total_outstanding: string;
  rows: AgingRow[];
  truncated: boolean;
}

export async function getAgingReport(bucket?: AgingBucketKey | null): Promise<AgingReport> {
  const { data } = await apiClient.get<AgingReport>('/api/reports/aging', { params: bucket ? { bucket } : {} });
  return data;
}

export async function downloadAgingCsv(bucket?: AgingBucketKey | null): Promise<Blob> {
  const { data } = await apiClient.get('/api/reports/aging/export', { params: bucket ? { bucket } : {}, responseType: 'blob' });
  return data as Blob;
}
