import { useEffect, useRef, useState } from 'react';
import { getNotificationSummary } from '../api/notifications';
import { useAuthStore } from '../store/authStore';

const POLL_INTERVAL_MS = 25_000;
const BASE_TITLE = 'Ledgr';

/**
 * Drives every "something arrived" indicator in the parent app from one
 * shared poll: the nav dot on Class group, the browser tab title (like
 * Gmail/WhatsApp Web showing "(2) Ledgr"), and — when installed as a PWA
 * on a platform that supports it (Chrome/Edge on Android and desktop) —
 * the actual OS-level badge on the app icon, via the Badging API. iOS
 * Safari has no Badging API at all, so that part just silently no-ops
 * there; the nav dot and tab title still work everywhere.
 *
 * Polls only for parent accounts (the backend endpoint is parent-only),
 * and pauses while the tab is hidden so it isn't burning battery/data in
 * a background tab.
 */
export function useUnreadNotifications() {
  const user = useAuthStore((s) => s.user);
  const isParent = user?.role === 'PARENT';
  const [unreadMessages, setUnreadMessages] = useState(0);
  const [unreadClassGroups, setUnreadClassGroups] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function poll() {
    try {
      const summary = await getNotificationSummary();
      setUnreadMessages(summary.unread_messages);
      setUnreadClassGroups(summary.unread_class_group_messages);
    } catch {
      // Silent — a failed poll just means the badge stays at its last
      // known value until the next tick, not worth surfacing an error for.
    }
  }

  useEffect(() => {
    if (!isParent) return;

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    function handleVisibility() {
      if (document.hidden) {
        if (intervalRef.current) clearInterval(intervalRef.current);
      } else {
        poll();
        intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
      }
    }
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isParent]);

  const total = unreadMessages + unreadClassGroups;

  useEffect(() => {
    document.title = total > 0 ? `(${total}) ${BASE_TITLE}` : BASE_TITLE;

    const nav = navigator as Navigator & {
      setAppBadge?: (count: number) => Promise<void>;
      clearAppBadge?: () => Promise<void>;
    };
    if (total > 0) {
      nav.setAppBadge?.(total).catch(() => {});
    } else {
      nav.clearAppBadge?.().catch(() => {});
    }
  }, [total]);

  // Reset the tab title on unmount so it doesn't linger stale if this
  // hook's consumer ever goes away without a full page reload.
  useEffect(() => {
    return () => {
      document.title = BASE_TITLE;
    };
  }, []);

  return { unreadMessages, unreadClassGroups, total, refresh: poll };
}
