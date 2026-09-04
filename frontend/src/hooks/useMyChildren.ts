import { useCallback, useEffect, useState } from 'react';
import { listMyChildren } from '../api/parent';
import type { ParentStudentView } from '../types';

export function useMyChildren() {
  const [children, setChildren] = useState<ParentStudentView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setError(null);
    try {
      const data = await listMyChildren();
      setChildren(data);
    } catch {
      setError('Could not load your children\'s records. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { children, loading, error, refetch };
}
