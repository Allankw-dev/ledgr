import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Bell, AtSign, BellRing, CheckCheck, Flag, MessageCircle, MessageSquare, Users2, type LucideIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import type { MentionNotification } from '../types';

/** How many unread items of each kind there are (what the badge number is made of). */
export interface UnreadCounts {
  messages: number;
  classGroups: number;
  direct: number;
  /** Open chat reports — only shown to the school admin. */
  chatReports?: number;
}

interface Props {
  total: number;
  /** When given, the dropdown lists each kind of unread item with a link to where it is. */
  counts?: UnreadCounts;
  unreadMentions: number;
  mentions: MentionNotification[];
  /** True once the first list has arrived. Until then an empty list means "not here yet", not "none". */
  mentionsLoaded?: boolean;
  mentionsFailed?: boolean;
  onOpen: () => void;
  onMarkSeen: (ids?: string[]) => Promise<void>;
}

function timeAgo(iso: string) {
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m`;
  if (mins < 1440) return `${Math.round(mins / 60)}h`;
  return `${Math.round(mins / 1440)}d`;
}

/** Bell with an unread badge and a dropdown: every kind of unread item, then "X mentioned you" items. */
export function NotificationBell({ total, counts, unreadMentions, mentions, mentionsLoaded = true, mentionsFailed = false, onOpen, onMarkSeen }: Props) {
  const navigate = useNavigate();
  const role = useAuthStore((s) => s.user?.role);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const isParent = role === 'PARENT';
  const chatPath = isParent ? '/parent/class-group' : '/class-groups';

  // One row per kind of unread item that has something waiting, each linking to where it lives.
  const rows: { key: string; label: string; count: number; icon: LucideIcon; to: string; amber?: boolean }[] = counts
    ? [
        { key: 'messages', label: 'School messages', count: role === 'TEACHER' ? 0 : counts.messages, icon: MessageSquare, to: isParent ? '/parent/dashboard' : '/messages' },
        { key: 'class', label: 'Class group chats', count: counts.classGroups, icon: Users2, to: chatPath },
        { key: 'direct', label: isParent ? 'Teacher chats' : 'Private chats', count: counts.direct, icon: MessageCircle, to: isParent ? '/parent/chats' : '/chats' },
        { key: 'reports', label: 'Chat reports to review', count: role === 'SCHOOL_ADMIN' ? counts.chatReports ?? 0 : 0, icon: Flag, to: '/chat-reports', amber: true },
      ].filter((r) => r.count > 0)
    : [];
  const canAskPermission = typeof Notification !== 'undefined' && Notification.permission === 'default';

  // The dropdown is drawn straight into <body> (see the portal below), so it is placed from the
  // bell's position on screen. It used to be absolutely positioned inside the page header, which
  // meant the page content (same z-index, later in the page) was painted on top of it, and on
  // 360px phones its fixed 320px width hung 20px off the left edge of the screen.
  const place = useCallback(() => {
    const btn = buttonRef.current;
    if (!btn) return;
    const margin = 12;
    const r = btn.getBoundingClientRect();
    const width = Math.min(320, window.innerWidth - margin * 2);
    // Right-align to the bell, then nudge so the whole dropdown stays inside the screen.
    const left = Math.min(Math.max(r.right - width, margin), window.innerWidth - width - margin);
    setPos({ top: r.bottom + 8, left, width });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true); // the page can scroll under an open dropdown
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [open, place]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const target = e.target as Node;
      // The dropdown lives outside the bell's DOM tree now, so check both.
      if (ref.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const badge = Math.max(total, unreadMentions);
  const unseen = mentions.filter((m) => !m.seen);

  return (
    <div className="relative" ref={ref}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          if (!open) onOpen();
        }}
        aria-label={badge > 0 ? `${badge} new notifications` : 'Notifications'}
        className="relative w-9 h-9 flex items-center justify-center rounded-full border border-ink-200 bg-panel/80 text-ink-700 hover:text-ink-900 hover:border-ink-600 transition-colors"
      >
        <Bell className="w-4.5 h-4.5" strokeWidth={2} />
        {badge > 0 && (
          <span
            className={`absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold flex items-center justify-center text-[#06110B] ${
              unreadMentions > 0 ? 'bg-amber ring-2 ring-amber/30' : 'bg-green'
            }`}
          >
            {badge > 99 ? '99+' : badge}
          </span>
        )}
      </button>

      {open && pos && createPortal(
        <div
          ref={menuRef}
          role="dialog"
          aria-label="Notifications"
          style={{ top: pos.top, left: pos.left, width: pos.width, maxHeight: `calc(100dvh - ${pos.top}px - 12px)` }}
          className="pop-in origin-top-right fixed z-[60] flex flex-col rounded-lg border border-ink-200 bg-panel shadow-2xl overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-ink-200">
            <p className="text-sm font-medium text-ink-900">Notifications</p>
            {unseen.length > 0 && (
              <button onClick={() => void onMarkSeen()} className="text-xs text-emerald-700 hover:underline">
                Mark all read
              </button>
            )}
          </div>

          <div className="min-h-0 max-h-80 overflow-y-auto">
            {rows.length > 0 && (
              <ul className="border-b border-ink-100">
                {rows.map(({ key, label, count, icon: Icon, to, amber }) => (
                  <li key={key}>
                    <button
                      onClick={() => {
                        setOpen(false);
                        navigate(to);
                      }}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-ink-100 transition-colors"
                    >
                      <span className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${amber ? 'bg-amber/15 text-amber' : 'bg-green/10 text-green'}`}>
                        <Icon className="w-4 h-4" strokeWidth={2} />
                      </span>
                      <span className="flex-1 min-w-0 text-sm text-ink-900 truncate">{label}</span>
                      <span className={`min-w-[22px] h-[22px] px-1.5 rounded-full text-[11px] font-bold flex items-center justify-center text-[#06110B] ${amber ? 'bg-amber' : 'bg-green'}`}>
                        {count > 99 ? '99+' : count}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {mentions.length > 0 ? (
              <>
                {rows.length > 0 && <p className="px-4 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-400">Mentions</p>}
                {mentions.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => {
                      setOpen(false);
                      // Go to the chat straight away; marking it read happens in the background.
                      if (!m.seen) void onMarkSeen([m.id]);
                      navigate(`${chatPath}?class=${m.class_id}`);
                    }}
                    className={`w-full text-left px-4 py-3 border-b border-ink-100 hover:bg-ink-100 transition-colors ${
                      m.seen ? '' : 'bg-amber/5'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs text-ink-900">
                        <span className="font-medium">{m.sender_name}</span> mentioned you in{' '}
                        <span className="font-medium">{m.class_name}</span>
                      </p>
                      <span className="text-[10px] text-ink-400 shrink-0">{timeAgo(m.created_at)}</span>
                    </div>
                    {m.preview && <p className="text-xs text-ink-600 truncate mt-0.5">{m.preview}</p>}
                  </button>
                ))}
              </>
            ) : !mentionsLoaded && mentionsFailed ? (
              rows.length === 0 && (
                <div className="px-4 py-8 text-center">
                  <p className="text-xs text-ink-600">Couldn't load your notifications.</p>
                  <button onClick={onOpen} className="mt-2 text-xs text-emerald-700 hover:underline">
                    Try again
                  </button>
                </div>
              )
            ) : !mentionsLoaded ? (
              rows.length === 0 && (
                <div className="px-4 py-8 text-center" role="status" aria-live="polite">
                  <AtSign className="w-6 h-6 text-ink-400 mx-auto mb-2 animate-pulse" strokeWidth={1.5} />
                  <p className="text-xs text-ink-600">Loading your notifications…</p>
                </div>
              )
            ) : (
              rows.length === 0 && (
                <div className="px-4 py-8 text-center">
                  <CheckCheck className="w-6 h-6 text-green mx-auto mb-2" strokeWidth={1.5} />
                  <p className="text-xs text-ink-600">You're all caught up.</p>
                </div>
              )
            )}
          </div>

          {canAskPermission && (
            <button
              onClick={() => Notification.requestPermission().then(() => setOpen(false))}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs text-ink-700 hover:bg-ink-100 border-t border-ink-200"
            >
              <BellRing className="w-3.5 h-3.5" strokeWidth={2} />
              Get desktop alerts when someone mentions you
            </button>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
}
