import { Link, useLocation } from 'react-router-dom';
import { MessageCircle, Users2 } from 'lucide-react';

/** Segmented switch between the two parent chat screens, with a gliding highlight. */
export function ChatTabs({ classUnread = 0, directUnread = 0 }: { classUnread?: number; directUnread?: number }) {
  const { pathname } = useLocation();
  const direct = pathname.startsWith('/parent/chats');
  const tabs = [
    { to: '/parent/class-group', label: 'Class group', icon: Users2, unread: classUnread },
    { to: '/parent/chats', label: 'Teacher chats', icon: MessageCircle, unread: directUnread },
  ];
  return (
    <div className="relative grid grid-cols-2 p-1 rounded-full bg-ink-100/70 ring-1 ring-white/5 mb-4 max-w-sm" role="tablist">
      <span
        aria-hidden="true"
        className="bottom-nav-pill absolute top-1 bottom-1 left-1 w-[calc(50%-4px)] rounded-full bg-emerald-100 ring-1 ring-green/25 shadow-[0_0_18px_-4px_rgba(57,255,136,0.5)]"
        style={{ transform: `translateX(${direct ? 100 : 0}%)` }}
      />
      {tabs.map(({ to, label, icon: Icon, unread }, i) => {
        const active = i === (direct ? 1 : 0);
        return (
          <Link
            key={to}
            to={to}
            role="tab"
            aria-selected={active}
            className={`relative z-10 flex items-center justify-center gap-1.5 py-2 text-sm font-medium transition-colors ${active ? 'text-green' : 'text-ink-600'}`}
          >
            <Icon className="w-4 h-4" strokeWidth={2} />
            {label}
            {unread > 0 && (
              <span className="min-w-[16px] h-4 px-1 rounded-full bg-green text-[#06110B] text-[10px] font-bold leading-4 text-center">{unread > 9 ? '9+' : unread}</span>
            )}
          </Link>
        );
      })}
    </div>
  );
}
