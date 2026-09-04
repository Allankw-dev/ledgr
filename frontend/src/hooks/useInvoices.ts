import { useCallback, useEffect, useState } from 'react';
import { listInvoices } from '../api/school';
import type { Invoice } from '../types';

export function useInvoices() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setInvoices(await listInvoices());
    } catch {
      setError('Could not load invoices. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { invoices, loading, error, refetch };
}
