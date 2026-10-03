import { useCallback, useEffect, useRef, useState } from 'react';
import type { ParentStudentView } from '../types';

const POLL_EVERY_MS = 3000;
const GIVE_UP_AFTER_MS = 90_000;
const SHOW_RECEIVED_FOR_MS = 8000;

function paidOf(child: ParentStudentView) {
  return child.invoices.reduce((s, i) => s + Number(i.amount_paid), 0);
}

function paidTotal(children: ParentStudentView[]) {
  return children.reduce((sum, c) => sum + paidOf(c), 0);
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
  // Which child's money we're waiting on / which child's balance just moved. Only filled in
  // when the parent has more than one child, so the banner can say whose payment it is.
  const [watchingFor, setWatchingFor] = useState<string | null>(null);
  const [receivedFor, setReceivedFor] = useState<string[]>([]);
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

  const watch = useCallback((childName?: string) => {
    window.clearInterval(timer.current);
    window.clearTimeout(hideTimer.current);
    const before = paidTotal(latest.current);
    const beforeByChild = new Map(latest.current.map((c) => [c.id, paidOf(c)]));
    const multiple = latest.current.length > 1;
    setWatchingFor(multiple && childName ? childName : null);
    setReceivedFor([]);
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
        setReceivedFor(
          multiple && data ? data.filter((c) => paidOf(c) > (beforeByChild.get(c.id) ?? 0)).map((c) => c.full_name) : []
        );
        hideTimer.current = window.setTimeout(() => {
          setReceived(null);
          setReceivedFor([]);
        }, SHOW_RECEIVED_FOR_MS);
      } else if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
        window.clearInterval(timer.current);
        setPolling(false);
      }
    }, POLL_EVERY_MS);
  }, [refetch]);

  return { polling, received, watchingFor, receivedFor, watch };
}
