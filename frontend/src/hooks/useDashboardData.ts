import { useEffect, useState } from 'react';
import { listInvoices, listStudents } from '../api/school';
import type { Invoice, Student } from '../types';

export function useDashboardData() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [invoiceData, studentData] = await Promise.all([listInvoices(), listStudents()]);
        if (!cancelled) {
          setInvoices(invoiceData);
          setStudents(studentData);
        }
      } catch {
        if (!cancelled) setError('Could not load dashboard data. Check your connection and try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { invoices, students, loading, error };
}
