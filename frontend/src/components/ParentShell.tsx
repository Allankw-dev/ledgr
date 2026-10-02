import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { BookOpen, FileText, Home, LogOut, MessageCircle, Receipt, Sparkles, UserRound } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';
import { useUnreadNotifications } from '../hooks/useUnreadNotifications';
import { BackButton } from './BackButton';
import { NotificationBell } from './NotificationBell';
import { BottomNav, type BottomNavItem } from './BottomNav';
import { BottomSheet } from './BottomSheet';

const navItems = [
  { to: '/parent/dashboard', label: 'Dashboard', badgeKey: 'unreadMessages' as const },
  { to: '/parent/invoices', label: 'Invoices' },
  { to: '/parent/receipts', label: 'Receipts' },
  { to: '/parent/class-group', label: 'Class group', badgeKey: 'unreadClassGroups' as const },
  { to: '/parent/chats', label: 'Teacher chats', badgeKey: 'unreadDirect' as const },
  { to: '/parent/assistant', label: 'Assistant' },
  { to: '/parent/profile', label: 'Profile' },
];

function TabBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-green text-[#06110B] text-[10px] font-bold leading-none">
      {count > 9 ? '9+' : count}
    </span>
  );
}

/** Desktop tabs: one glowing pill glides to whichever tab is current. */
function DesktopTabs({ counts }: { counts: Record<string, number> }) {
  const { pathname } = useLocation();
  const refs = useRef<(HTMLAnchorElement | null)[]>([]);
  const [glider, setGlider] = useState({ left: 0, width: 0, ready: false });
  const activeIdx = navItems.findIndex((i) => pathname.startsWith(i.to));
  const sig = JSON.stringify(counts);

  useLayoutEffect(() => {
    function measure() {
      const el = refs.current[activeIdx];
      setGlider(el ? { left: el.offsetLeft, width: el.offsetWidth, ready: true } : (g) => ({ ...g, ready: false }));
    }
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [activeIdx, sig]);

  return (
    <nav aria-label="Main" className="relative inline-flex items-center gap-0.5 p-1 rounded-full bg-ink-100/70 ring-1 ring-white/5">
      <span
        aria-hidden="true"
        className="tab-glider absolute top-1 bottom-1 rounded-full bg-emerald-100 ring-1 ring-green/25 shadow-[0_0_18px_-4px_rgba(57,255,136,0.5)]"
        style={{ left: glider.left, width: glider.width, opacity: glider.ready ? 1 : 0 }}
      />
      {navItems.map(({ to, label, badgeKey }, i) => {
        const active = i === activeIdx;
        return (
          <Link
            key={to}
            to={to}
            ref={(el) => {
              refs.current[i] = el;
            }}
            aria-current={active ? 'page' : undefined}
            className={`relative z-10 px-3.5 py-1.5 rounded-full text-sm font-medium whitespace-nowrap flex items-center transition-colors ${
              active ? 'text-green' : 'text-ink-600 hover:text-ink-900'
            }`}
          >
            {label}
            {badgeKey && <TabBadge count={counts[badgeKey] ?? 0} />}
          </Link>
        );
      })}
    </nav>
  );
}

export function ParentShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { unreadMessages, unreadClassGroups, unreadDirect, unreadMentions, mentions, total, loadMentions, markSeen } = useUnreadNotifications();
  const [sheetOpen, setSheetOpen] = useState(false);

  function handleLogout() {
    setSheetOpen(false);
    logout();
    navigate('/login');
  }

  const displayName = user?.full_name || user?.email || '';
  const initial = displayName.trim().charAt(0).toUpperCase() || '?';

  const bottomItems: BottomNavItem[] = [
    { label: 'Home', to: '/parent/dashboard', icon: Home, badge: unreadMessages },
    { label: 'Invoices', to: '/parent/invoices', icon: FileText },
    { label: 'Ask', to: '/parent/assistant', icon: Sparkles, center: true },
    { label: 'Chats', to: '/parent/class-group', also: ['/parent/chats'], icon: MessageCircle, badge: unreadClassGroups + unreadDirect },
    { label: 'Receipts', to: '/parent/receipts', icon: Receipt },
  ];

  return (
    <div className="min-h-dvh relative">
      <header className="relative z-10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shadow-[0_6px_18px_-4px_rgba(57,255,136,0.55)]">
              <BookOpen className="w-4 h-4 text-[#06110B]" strokeWidth={2.25} />
            </div>
            <span className="font-display text-lg font-semibold tracking-tight">Ledgr</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <BackButton className="!px-3 !py-1.5" />
            <NotificationBell total={total} unreadMentions={unreadMentions} mentions={mentions} onOpen={loadMentions} onMarkSeen={markSeen} />
            <span className="text-sm text-ink-600 hidden md:inline truncate">{displayName}</span>
            <button
              onClick={handleLogout}
              aria-label="Sign out"
              className="hidden md:flex items-center gap-1.5 text-sm text-ink-600 hover:text-ink-900 transition-colors"
            >
              <LogOut className="w-4 h-4" strokeWidth={2} />
              Sign out
            </button>
            {/* Phone: avatar opens the account sheet (profile + sign out). */}
            <button
              onClick={() => setSheetOpen(true)}
              aria-label="Account menu"
              className="md:hidden w-9 h-9 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] text-sm font-bold flex items-center justify-center ring-2 ring-white/10"
            >
              {initial}
            </button>
          </div>
        </div>
      </header>

      {/* Desktop tabs, pinned under the top edge while scrolling. Phones use the bottom dock instead. */}
      <div className="hidden md:block sticky top-0 z-20 glass-bar">
        <div className="max-w-3xl mx-auto px-6 py-2 flex justify-center">
          <DesktopTabs counts={{ unreadMessages, unreadClassGroups, unreadDirect }} />
        </div>
      </div>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-4 md:pt-8 pb-32 md:pb-24 relative z-10">
        <div key={location.pathname} className="page-enter">
          {children}
        </div>
      </main>

      <BottomNav items={bottomItems} />
      <AssistantFab to="/parent/assistant" />

      <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Account">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] text-lg font-bold flex items-center justify-center">{initial}</div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink-900 truncate">{user?.full_name || 'Parent'}</p>
            <p className="text-xs text-ink-600 truncate">{user?.email}</p>
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Link
            to="/parent/profile"
            onClick={() => setSheetOpen(false)}
            className="flex items-center gap-3 px-3.5 py-3 rounded-xl bg-ink-100/70 text-sm font-medium text-ink-900 active:bg-ink-200"
          >
            <UserRound className="w-5 h-5 text-green" strokeWidth={1.75} />
            Profile and children
          </Link>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3.5 py-3 rounded-xl bg-ink-100/70 text-sm font-medium text-clay-700 active:bg-ink-200 text-left"
          >
            <LogOut className="w-5 h-5" strokeWidth={1.75} />
            Sign out
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
