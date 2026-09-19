import { useEffect, useRef } from 'react';

/**
 * Calls `callback` every `intervalMs` while `enabled` is true.
 *
 * Compared with a bare setInterval this is much kinder to the server:
 *  - it waits for the previous request to finish before scheduling the next,
 *    so a slow/overloaded API never gets a growing pile of overlapping polls;
 *  - it skips the request while the browser tab is hidden (nobody is looking),
 *    and refreshes immediately when the tab becomes visible again;
 *  - errors are swallowed — a missed poll isn't worth surfacing to the user.
 */
export function usePolling(callback: () => Promise<unknown> | void, intervalMs: number, enabled = true) {
  const callbackRef = useRef(callback);
  useEffect(() => {
    callbackRef.current = callback;
  });

  useEffect(() => {
    if (!enabled) return;

    let stopped = false;
    let inFlight = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function run() {
      if (stopped || inFlight || document.hidden) return;
      inFlight = true;
      try {
        await callbackRef.current();
      } catch {
        /* ignore — next tick will try again */
      } finally {
        inFlight = false;
      }
    }

    function schedule() {
      timer = setTimeout(async () => {
        await run();
        if (!stopped) schedule();
      }, intervalMs);
    }

    function handleVisibility() {
      if (!document.hidden) void run();
    }

    schedule();
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [intervalMs, enabled]);
}
