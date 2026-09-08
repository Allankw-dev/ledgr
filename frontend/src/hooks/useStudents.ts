import { useCallback, useEffect, useState } from 'react';
import { listStudents } from '../api/school';
import type { Student, PageMeta } from '../types';

const PAGE_SIZE = 25;

export function useStudents(classId?: string) {
  const [students, setStudents] = useState<Student[]>([]);
  const [meta, setMeta] = useState<PageMeta | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listStudents(page, PAGE_SIZE, classId);
      setStudents(data.items);
      setMeta(data.meta);
    } catch {
      setError('Could not load students. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, [page, classId]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { students, meta, page, setPage, loading, error, refetch };
}
