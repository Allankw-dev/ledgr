import { useCallback, useEffect, useState } from 'react';
import { listTerms, listClasses, listFeeStructures } from '../api/school';
import type { Term, SchoolClass, FeeStructure } from '../types';

export function useTerms() {
  const [terms, setTerms] = useState<Term[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true);
    try {
      setTerms(await listTerms());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { terms, loading, refetch };
}

export function useClasses() {
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true);
    try {
      setClasses(await listClasses());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { classes, loading, refetch };
}

export function useFeeStructures(termId: string | undefined) {
  const [feeStructures, setFeeStructures] = useState<FeeStructure[]>([]);
  const [loading, setLoading] = useState(false);

  const refetch = useCallback(async () => {
    if (!termId) {
      setFeeStructures([]);
      return;
    }
    setLoading(true);
    try {
      setFeeStructures(await listFeeStructures(termId));
    } finally {
      setLoading(false);
    }
  }, [termId]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { feeStructures, loading, refetch };
}
