import { useCallback, useEffect, useState } from 'react';
import { listStudents } from '../api/school';
import type { Student } from '../types';

export function useStudents() {
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listStudents();
      setStudents(data);
    } catch {
      setError('Could not load students. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { students, loading, error, refetch };
}
