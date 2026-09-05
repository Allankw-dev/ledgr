import { useCallback, useEffect, useState } from 'react';
import { listInvoices } from '../api/school';
import type { InvoiceListItem, PageMeta } from '../types';

const DEFAULT_PAGE_SIZE = 25;

export function useInvoices(termId?: string, status?: string, pageSize = DEFAULT_PAGE_SIZE) {
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [meta, setMeta] = useState<PageMeta | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listInvoices(page, pageSize, status, termId);
      setInvoices(data.items);
      setMeta(data.meta);
    } catch {
      setError('Could not load invoices. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, status, termId]);

  // A change of term/status is a new query, not a next page of the old one.
  useEffect(() => {
    setPage(1);
  }, [termId, status]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { invoices, meta, page, setPage, loading, error, refetch };
}
