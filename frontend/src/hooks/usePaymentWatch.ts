import { useCallback, useEffect, useRef, useState } from 'react';
import type { ParentStudentView } from '../types';

const POLL_EVERY_MS = 3000;
const GIVE_UP_AFTER_MS = 90_000;
const SHOW_RECEIVED_FOR_MS = 8000;

function paidTotal(children: ParentStudentView[]) {
  return children.reduce((sum, c) => sum + c.invoices.reduce((s, i) => s + Number(i.amount_paid), 0), 0);
}

/**
 * After an M-Pesa prompt is sent, the money arrives asynchronously (Safaricom
 * calls the server once the parent enters their PIN). This checks for the
 * updated figures every few seconds and stops the moment the amount paid goes
 * up, then reports how much just came in so the balances can visibly update.
 */
export function usePaymentWatch(
  children: ParentStudentView[],
  refetch: () => Promise<ParentStudentView[] | undefined>
) {
  const [polling, setPolling] = useState(false);
  const [received, setReceived] = useState<number | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const hideTimer = useRef<number | undefined>(undefined);
  const latest = useRef(children);
  latest.current = children;

  useEffect(
    () => () => {
      window.clearInterval(timer.current);
      window.clearTimeout(hideTimer.current);
    },
    []
  );

  const watch = useCallback(() => {
    window.clearInterval(timer.current);
    window.clearTimeout(hideTimer.current);
    const before = paidTotal(latest.current);
    const startedAt = Date.now();
    setPolling(true);
    setReceived(null);

    timer.current = window.setInterval(async () => {
      const data = await refetch();
      const after = data ? paidTotal(data) : before;
      if (after > before) {
        window.clearInterval(timer.current);
        setPolling(false);
        setReceived(after - before);
        hideTimer.current = window.setTimeout(() => setReceived(null), SHOW_RECEIVED_FOR_MS);
      } else if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
        window.clearInterval(timer.current);
        setPolling(false);
      }
    }, POLL_EVERY_MS);
  }, [refetch]);

  return { polling, received, watch };
}
