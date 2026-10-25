import { useEffect, useState } from 'react';
import { getMySubscription, type Subscription } from '../api/subscription';

/** The school's standing, for the banner. Looked up once when the staff shell opens; a failure just means no banner. */
export function useSubscription(enabled: boolean): Subscription | null {
  const [sub, setSub] = useState<Subscription | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    getMySubscription()
      .then((s) => !cancelled && setSub(s))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [enabled]);
  return sub;
}
