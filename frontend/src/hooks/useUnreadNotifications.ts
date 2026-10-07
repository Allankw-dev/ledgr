import { useCallback, useEffect, useRef, useState } from 'react';
import { getAllNotificationsSummary, listMentions, markMentionsSeen } from '../api/notifications';
import { useAuthStore } from '../store/authStore';
import { usePolling } from './usePolling';
import type { MentionNotification } from '../types';

const POLL_INTERVAL_MS = 25_000;
const BASE_TITLE = 'Ledgr';

/**
 * One shared poll (every role) that drives every "something arrived"
 * indicator: the nav badges, the notification bell, the browser tab title
 * (like WhatsApp Web's "(2) Ledgr"), the OS app-icon badge when installed as
 * a PWA, and a desktop notification when someone @mentions you (if the person
 * allowed notifications). Pauses in hidden tabs and never overlaps requests
 * (see usePolling). Polling also tells senders their message was delivered.
 */
export function useUnreadNotifications() {
  const user = useAuthStore((s) => s.user);
  const enabled = !!user;
  const [unreadMessages, setUnreadMessages] = useState(0);
  const [unreadClassGroups, setUnreadClassGroups] = useState(0);
  const [unreadMentions, setUnreadMentions] = useState(0);
  const [unreadDirect, setUnreadDirect] = useState(0);
  const [openChatReports, setOpenChatReports] = useState(0);
  const [mentions, setMentions] = useState<MentionNotification[]>([]);
  // The server can take a few seconds to answer. Until the first list arrives the bell must say
  // "loading" — not "Nobody has mentioned you yet", which is a claim, and a wrong one.
  const [mentionsLoaded, setMentionsLoaded] = useState(false);
  const [mentionsLoading, setMentionsLoading] = useState(false);
  const [mentionsFailed, setMentionsFailed] = useState(false);
  const lastMentionCount = useRef<number | null>(null);
  const mentionsRef = useRef<MentionNotification[]>([]);
  mentionsRef.current = mentions;

  const loadMentions = useCallback(async () => {
    setMentionsLoading(true);
    try {
      setMentions(await listMentions());
      setMentionsLoaded(true);
      setMentionsFailed(false);
    } catch {
      setMentionsFailed(true); // keep whatever list we already had
    } finally {
      setMentionsLoading(false);
    }
  }, []);

  const poll = useCallback(async () => {
    try {
      const s = await getAllNotificationsSummary();
      setUnreadMessages(s.unread_messages);
      setUnreadClassGroups(s.unread_class_group_messages);
      setUnreadMentions(s.unread_mentions);
      setUnreadDirect(s.unread_direct_messages ?? 0);
      setOpenChatReports(s.open_chat_reports ?? 0);

      const previous = lastMentionCount.current;
      lastMentionCount.current = s.unread_mentions;
      if (s.unread_mentions > 0 && (previous === null || s.unread_mentions > previous)) {
        const list = await listMentions();
        setMentions(list);
        setMentionsLoaded(true);
        setMentionsFailed(false);
        // Only interrupt with a desktop notification for a NEW mention, not on first load.
        if (previous !== null && typeof Notification !== 'undefined' && Notification.permission === 'granted') {
          const newest = list.find((m) => !m.seen);
          if (newest) {
            new Notification(`${newest.sender_name} mentioned you in ${newest.class_name}`, {
              body: newest.preview,
              tag: `mention-${newest.id}`,
            });
          }
        }
      }
    } catch {
      /* a failed poll just leaves the badges at their last value */
    }
  }, []);

  useEffect(() => {
    if (enabled) void poll();
  }, [enabled, poll]);
  usePolling(poll, POLL_INTERVAL_MS, enabled);

  // Optimistic: the badge and the list change the instant the person taps, and the server is
  // told in the background. (It used to wait for the request AND two refetches before anything
  // changed — on a slow connection that was several seconds of a tap that seemed to do nothing.)
  // The returned promise settles when the server has caught up; callers should not await it
  // before navigating.
  const markSeen = useCallback(
    async (ids?: string[]) => {
      const wasUnseen = mentionsRef.current.filter((m) => !m.seen && (!ids || ids.includes(m.id))).length;
      setMentions((prev) => prev.map((m) => (!ids || ids.includes(m.id) ? { ...m, seen: true } : m)));
      setUnreadMentions((prev) => {
        const next = ids ? Math.max(0, prev - wasUnseen) : 0;
        lastMentionCount.current = next; // so the next poll doesn't mistake this for a new mention
        return next;
      });
      try {
        await markMentionsSeen(ids);
      } catch {
        /* the refresh below puts the true numbers back if the server didn't take it */
      }
      void poll();
      void loadMentions();
    },
    [poll, loadMentions]
  );

  const total = unreadMessages + unreadClassGroups + unreadDirect;

  useEffect(() => {
    document.title = total > 0 ? `(${total}) ${BASE_TITLE}` : BASE_TITLE;
    const nav = navigator as Navigator & {
      setAppBadge?: (count: number) => Promise<void>;
      clearAppBadge?: () => Promise<void>;
    };
    if (total > 0) nav.setAppBadge?.(total).catch(() => {});
    else nav.clearAppBadge?.().catch(() => {});
  }, [total]);

  useEffect(() => {
    return () => {
      document.title = BASE_TITLE;
    };
  }, []);

  return {
    unreadMessages, unreadClassGroups, unreadDirect, openChatReports, unreadMentions, mentions,
    mentionsLoaded, mentionsLoading, mentionsFailed,
    total, refresh: poll, loadMentions, markSeen,
  };
}
