import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

export interface TermCollectionPoint {
  term_id: string;
  term_name: string;
  total_billed: string;
  total_paid: string;
}

export interface TopRiskInvoice {
  invoice_id: string;
  student_id: string;
  student_name: string;
  class_name: string;
  balance: string;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high';
}

interface DashboardAnalytics {
  total_collected: string;
  total_outstanding: string;
  overdue_count: number;
  active_student_count: number;
  collection_by_term: TermCollectionPoint[];
  top_risk: TopRiskInvoice[];
}

export function useDashboardAnalytics() {
  const [data, setData] = useState<DashboardAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<DashboardAnalytics>('/api/reports/analytics')
      .then(({ data }) => {
        if (!cancelled) setData(data);
      })
      .catch(() => {
        // Non-critical enhancement — the rest of the dashboard still works without it
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading };
}
