import { useEffect, useRef, type ReactNode } from 'react';
import { Link, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { BookOpen, LogOut, Sparkles } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';
import { useUnreadNotifications } from '../hooks/useUnreadNotifications';
import { BackButton } from './BackButton';
import { NotificationBell } from './NotificationBell';

const navItems = [
  { to: '/parent/dashboard', label: 'Dashboard', badgeKey: 'unreadMessages' as const },
  { to: '/parent/invoices', label: 'Invoices' },
  { to: '/parent/receipts', label: 'Receipts' },
  { to: '/parent/class-group', label: 'Class group', badgeKey: 'unreadClassGroups' as const },
  { to: '/parent/chats', label: 'Teacher chats', badgeKey: 'unreadDirect' as const },
  { to: '/parent/assistant', label: 'Assistant' },
  { to: '/parent/profile', label: 'Profile' },
];

function NavBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-emerald-700 text-[#06110B] text-[10px] font-semibold leading-none">
      {count > 9 ? '9+' : count}
    </span>
  );
}

export function ParentShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { unreadMessages, unreadClassGroups, unreadDirect, unreadMentions, mentions, total, loadMentions, markSeen } = useUnreadNotifications();
  const badgeCounts = { unreadMessages, unreadClassGroups, unreadDirect };
  const navRef = useRef<HTMLElement>(null);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  // On a phone the tab row scrolls sideways; make sure the current tab is
  // always in view instead of hiding off the right edge.
  useEffect(() => {
    const active = navRef.current?.querySelector<HTMLElement>('[aria-current="page"]');
    active?.scrollIntoView({ inline: 'center', block: 'nearest' });
  }, [location.pathname]);

  const onAssistant = location.pathname === '/parent/assistant';

  return (
    <div className="min-h-dvh relative">
      <header className="relative z-10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-[#06110B]" strokeWidth={2} />
            </div>
            <span className="font-display text-lg font-semibold">Ledgr</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <BackButton className="!px-3 !py-1.5" />
            {!onAssistant && (
              <Link
                to="/parent/assistant"
                aria-label="Ask Ledgr"
                title="Ask Ledgr"
                className="md:hidden w-9 h-9 rounded-full border border-ink-200 bg-panel/80 flex items-center justify-center text-emerald-700"
              >
                <Sparkles className="w-4.5 h-4.5" strokeWidth={1.75} />
              </Link>
            )}
            <NotificationBell total={total} unreadMentions={unreadMentions} mentions={mentions} onOpen={loadMentions} onMarkSeen={markSeen} />
            <span className="text-sm text-ink-600 hidden sm:inline truncate">{user?.full_name || user?.email}</span>
            <button
              onClick={handleLogout}
              aria-label="Sign out"
              className="flex items-center gap-1.5 text-sm text-ink-600 hover:text-ink-900 transition-colors p-1.5 -mr-1.5"
            >
              <LogOut className="w-5 h-5 sm:w-4 sm:h-4" strokeWidth={2} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Tabs stay pinned under the top edge while scrolling. The fade on the
          right tells people on a phone there are more tabs to swipe to. */}
      <div className="sticky top-0 z-20 border-b border-ink-200 bg-paper/85 backdrop-blur-md">
        <div className="relative max-w-3xl mx-auto">
          <nav ref={navRef} className="px-4 sm:px-6 flex gap-1 overflow-x-auto scrollbar-none">
            {navItems.map(({ to, label, badgeKey }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `shrink-0 px-3 py-3 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center whitespace-nowrap ${
                    isActive
                      ? 'border-emerald-700 text-ink-900'
                      : 'border-transparent text-ink-600 hover:text-ink-900'
                  }`
                }
              >
                {label}
                {badgeKey && <NavBadge count={badgeCounts[badgeKey]} />}
              </NavLink>
            ))}
          </nav>
          <div className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-paper to-transparent md:hidden" aria-hidden="true" />
        </div>
      </div>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-6 sm:pt-8 pb-[max(2rem,env(safe-area-inset-bottom))] md:pb-24 relative z-10">
        <div key={location.pathname} className="page-enter">
          {children}
        </div>
      </main>
      <AssistantFab to="/parent/assistant" />
    </div>
  );
}
