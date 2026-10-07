import { useState, type ReactNode } from 'react';
import { Link, NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  BookOpen,
  FileText,
  Home,
  LayoutGrid,
  LogOut,
  Menu,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
  Receipt,
  Sparkles,
  UserRound,
  Users2,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';
import { useUnreadNotifications } from '../hooks/useUnreadNotifications';
import { useSidebarCollapsed } from '../hooks/useSidebarCollapsed';
import { BackButton } from './BackButton';
import { NotificationBell } from './NotificationBell';
import { BottomNav, type BottomNavItem } from './BottomNav';
import { BottomSheet } from './BottomSheet';

type BadgeKey = 'unreadMessages' | 'unreadClassGroups' | 'unreadDirect';

const navItems: { to: string; label: string; icon: LucideIcon; badgeKey?: BadgeKey }[] = [
  { to: '/parent/dashboard', label: 'Dashboard', icon: LayoutGrid, badgeKey: 'unreadMessages' },
  { to: '/parent/invoices', label: 'Invoices', icon: FileText },
  { to: '/parent/receipts', label: 'Receipts', icon: Receipt },
  { to: '/parent/class-group', label: 'Class group', icon: Users2, badgeKey: 'unreadClassGroups' },
  { to: '/parent/chats', label: 'Teacher chats', icon: MessageCircle, badgeKey: 'unreadDirect' },
  { to: '/parent/assistant', label: 'Assistant', icon: Sparkles },
  { to: '/parent/profile', label: 'Profile', icon: UserRound },
];

export function ParentShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { unreadMessages, unreadClassGroups, unreadDirect, unreadMentions, mentions, mentionsLoaded, mentionsFailed, total, loadMentions, markSeen } = useUnreadNotifications();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [collapsed, toggleCollapsed] = useSidebarCollapsed('ledgr.sidebar.parent');

  const counts: Record<BadgeKey, number> = { unreadMessages, unreadClassGroups, unreadDirect };

  function handleLogout() {
    setSheetOpen(false);
    setDrawerOpen(false);
    logout();
    navigate('/login');
  }

  const displayName = user?.full_name || user?.email || '';
  const initial = displayName.trim().charAt(0).toUpperCase() || '?';

  /** The same panel serves the desktop rail (can retract) and the phone drawer (always open). */
  function renderPanel(isCollapsed: boolean, onNavigate?: () => void) {
    return (
      <>
        <div className={`flex items-center py-6 mb-1 ${isCollapsed ? 'justify-center px-3' : 'gap-2.5 px-6'}`}>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shrink-0 shadow-[0_6px_18px_-4px_rgba(57,255,136,0.55)]">
            <BookOpen className="w-[18px] h-[18px] text-[#06110B]" strokeWidth={2.25} />
          </div>
          {!isCollapsed && <span className="font-display text-xl font-semibold tracking-tight">Ledgr</span>}
          {onNavigate && (
            <button onClick={onNavigate} aria-label="Close menu" className="ml-auto text-ink-600 hover:text-ink-900 md:hidden">
              <X className="w-5 h-5" strokeWidth={2} />
            </button>
          )}
        </div>

        <nav aria-label="Main" className="flex-1 px-3 flex flex-col gap-0.5 overflow-y-auto overflow-x-hidden pb-4">
          {navItems.map(({ to, label, icon: Icon, badgeKey }) => {
            const count = badgeKey ? counts[badgeKey] : 0;
            return (
              <NavLink
                key={to}
                to={to}
                title={isCollapsed ? label : undefined}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `side-link flex items-center px-2 py-2 rounded-xl text-sm font-medium ${
                    isActive ? 'text-ink-900' : 'text-ink-600 hover:text-ink-900 hover:bg-ink-100/70'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={`relative w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                        isActive ? 'bg-green/15 text-green' : 'bg-ink-100/80 text-ink-600'
                      }`}
                    >
                      <Icon className="w-[18px] h-[18px]" strokeWidth={isActive ? 2.25 : 1.75} />
                      {isCollapsed && count > 0 && <span className="pop-in absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-green ring-2 ring-[#0A0C16]" />}
                    </span>
                    <span
                      className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${
                        isCollapsed ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'
                      }`}
                    >
                      {label}
                    </span>
                    {!isCollapsed && count > 0 && (
                      <span className="pop-in ml-auto min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-bold flex items-center justify-center text-[#06110B] bg-green">
                        {count > 99 ? '99+' : count}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className="px-3 py-4 border-t border-white/[0.07] flex flex-col gap-1">
          {/* Retract / expand — desktop only (the phone drawer just closes). */}
          {!onNavigate && (
            <button
              onClick={toggleCollapsed}
              aria-label={isCollapsed ? 'Expand side panel' : 'Retract side panel'}
              title={isCollapsed ? 'Expand' : 'Retract'}
              className="flex items-center px-2 py-2 rounded-xl text-sm font-medium text-ink-600 hover:bg-ink-100/70 hover:text-ink-900 transition-colors"
            >
              <span className="w-8 h-8 rounded-lg bg-ink-100/80 flex items-center justify-center shrink-0">
                {isCollapsed ? <PanelLeftOpen className="w-[18px] h-[18px]" strokeWidth={1.75} /> : <PanelLeftClose className="w-[18px] h-[18px]" strokeWidth={1.75} />}
              </span>
              <span className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${isCollapsed ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>Retract</span>
            </button>
          )}
          <Link
            to="/parent/profile"
            onClick={onNavigate}
            title={isCollapsed ? displayName : undefined}
            className="flex items-center px-2 py-2 rounded-xl hover:bg-ink-100/70 transition-colors"
          >
            <span className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] text-sm font-bold flex items-center justify-center shrink-0">{initial}</span>
            <span className={`min-w-0 overflow-hidden transition-all duration-300 ${isCollapsed ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>
              <span className="block text-sm font-medium truncate text-ink-900">{displayName}</span>
              <span className="block text-xs text-ink-400">Parent</span>
            </span>
          </Link>
          <button
            onClick={handleLogout}
            title={isCollapsed ? 'Sign out' : undefined}
            className="flex items-center px-2 py-2 rounded-xl text-sm font-medium text-ink-600 hover:bg-ink-100/70 hover:text-ink-900 transition-colors"
          >
            <span className="w-8 h-8 flex items-center justify-center shrink-0">
              <LogOut className="w-[18px] h-[18px]" strokeWidth={2} />
            </span>
            <span className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${isCollapsed ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>Sign out</span>
          </button>
        </div>
      </>
    );
  }

  const bottomItems: BottomNavItem[] = [
    { label: 'Home', to: '/parent/dashboard', icon: Home, badge: unreadMessages },
    { label: 'Invoices', to: '/parent/invoices', icon: FileText },
    { label: 'Ask', to: '/parent/assistant', icon: Sparkles, center: true },
    { label: 'Chats', to: '/parent/class-group', also: ['/parent/chats'], icon: MessageCircle, badge: unreadClassGroups + unreadDirect },
    { label: 'Receipts', to: '/parent/receipts', icon: Receipt },
  ];

  return (
    <div className="min-h-dvh flex relative">
      {/* Desktop side panel: sticky, and it retracts to an icon rail. */}
      <aside
        className={`hidden md:flex md:flex-col sticky top-0 h-dvh self-start shrink-0 z-20 border-r border-white/[0.07] bg-paper/55 backdrop-blur-xl overflow-x-hidden transition-[width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          collapsed ? 'w-[72px]' : 'w-64'
        }`}
      >
        {renderPanel(collapsed)}
      </aside>

      {/* Phone drawer. */}
      {drawerOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="modal-backdrop-in absolute inset-0 bg-ink-950/60" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
          <aside className="drawer-in relative w-72 max-w-[85vw] bg-paper border-r border-white/10 flex flex-col h-full shadow-[20px_0_50px_-10px_rgba(0,0,0,0.8)]">
            {renderPanel(false, () => setDrawerOpen(false))}
          </aside>
        </div>
      )}

      <div className="flex-1 min-w-0 relative">
        <header className="relative z-10">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 shrink-0 md:invisible">
              <button
                onClick={() => setDrawerOpen(true)}
                aria-label="Open menu"
                className="md:hidden w-9 h-9 -ml-1.5 rounded-full flex items-center justify-center text-ink-900 active:bg-ink-100"
              >
                <Menu className="w-5 h-5" strokeWidth={2} />
              </button>
              <div className="md:hidden flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shadow-[0_6px_18px_-4px_rgba(57,255,136,0.55)]">
                  <BookOpen className="w-4 h-4 text-[#06110B]" strokeWidth={2.25} />
                </div>
                <span className="font-display text-lg font-semibold tracking-tight">Ledgr</span>
              </div>
            </div>
            <div className="flex items-center gap-2 sm:gap-4 min-w-0">
              <BackButton className="!px-3 !py-1.5" />
              <NotificationBell total={total} unreadMentions={unreadMentions} mentions={mentions} mentionsLoaded={mentionsLoaded} mentionsFailed={mentionsFailed} onOpen={loadMentions} onMarkSeen={markSeen} />
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

        <main className="max-w-4xl mx-auto px-4 sm:px-6 pt-2 md:pt-4 pb-32 md:pb-24 relative z-10">
          <div key={location.pathname} className="page-enter">
            {children}
          </div>
        </main>
      </div>

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
