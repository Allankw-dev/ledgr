import { useEffect, useRef, useState } from 'react';
import { Bell, AtSign, BellRing } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import type { MentionNotification } from '../types';

interface Props {
  total: number;
  unreadMentions: number;
  mentions: MentionNotification[];
  onOpen: () => void;
  onMarkSeen: (ids?: string[]) => Promise<void>;
}

function timeAgo(iso: string) {
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m`;
  if (mins < 1440) return `${Math.round(mins / 60)}h`;
  return `${Math.round(mins / 1440)}d`;
}

/** Bell with an unread badge and a dropdown of "X mentioned you" items. */
export function NotificationBell({ total, unreadMentions, mentions, onOpen, onMarkSeen }: Props) {
  const navigate = useNavigate();
  const role = useAuthStore((s) => s.user?.role);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const chatPath = role === 'PARENT' ? '/parent/class-group' : '/class-groups';
  const canAskPermission = typeof Notification !== 'undefined' && Notification.permission === 'default';

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const badge = Math.max(total, unreadMentions);
  const unseen = mentions.filter((m) => !m.seen);

  return (
    <div className="relative" ref={ref}>
      <button
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

      {open && (
        <div className="absolute right-0 mt-2 w-80 max-w-[90vw] z-50 rounded-lg border border-ink-200 bg-panel shadow-2xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-ink-200">
            <p className="text-sm font-medium text-ink-900">Mentions</p>
            {unseen.length > 0 && (
              <button onClick={() => onMarkSeen()} className="text-xs text-emerald-700 hover:underline">
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {mentions.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <AtSign className="w-6 h-6 text-ink-400 mx-auto mb-2" strokeWidth={1.5} />
                <p className="text-xs text-ink-600">Nobody has mentioned you yet.</p>
              </div>
            ) : (
              mentions.map((m) => (
                <button
                  key={m.id}
                  onClick={async () => {
                    setOpen(false);
                    if (!m.seen) await onMarkSeen([m.id]);
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
              ))
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
        </div>
      )}
    </div>
  );
}
