import { useCallback, useEffect, useState } from 'react';
import { listStudents } from '../api/school';
import type { Student } from '../types';

const PAGE_SIZE = 100; // server max
const MAX_PAGES = 50; // safety stop (5,000 students)

/**
 * Loads every active student (all pages), already ordered by grade then name
 * by the API, so the page can show one cluster per class without a cluster
 * being cut in half by pagination.
 */
export function useStudents(classIds?: string[]) {
  const classKey = (classIds ?? []).join(',');
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const ids = classKey ? classKey.split(',') : undefined;
      const all: Student[] = [];
      for (let page = 1; page <= MAX_PAGES; page++) {
        const data = await listStudents(page, PAGE_SIZE, ids);
        all.push(...data.items);
        if (!data.meta.has_more) break;
      }
      setStudents(all);
    } catch {
      setError('Could not load students. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, [classKey]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { students, loading, error, refetch };
}
