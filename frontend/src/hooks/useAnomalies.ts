import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

export interface PaymentAnomaly {
  payment_id: string;
  student_id: string;
  amount: string;
  paid_at: string | null;
  reasons: string[];
  severity: 'medium' | 'high';
  ml_anomaly_score?: number | null;
}

export function useAnomalies() {
  const [anomalies, setAnomalies] = useState<PaymentAnomaly[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<PaymentAnomaly[]>('/api/payments/anomalies')
      .then(({ data }) => {
        if (!cancelled) setAnomalies(data);
      })
      .catch(() => {
        // Non-critical enhancement — fail silently, dashboard still works without it
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { anomalies, loading };
}
