import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { BookOpen, LayoutGrid, Users, FileText, ShieldCheck, UserCheck, LogOut, Sparkles, Megaphone, ScrollText, MessageCircle, GraduationCap, Users2, Menu, X, MessagesSquare, Flag, Pencil, PanelLeftClose, PanelLeftOpen, Search, RefreshCw, type LucideIcon } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';
import { BackButton } from './BackButton';
import { NotificationBell, type BellItem } from './NotificationBell';
import { BottomNav, type BottomNavItem } from './BottomNav';
import { useUnreadNotifications } from '../hooks/useUnreadNotifications';
import { useSidebarCollapsed } from '../hooks/useSidebarCollapsed';
import { Modal } from './ui/Modal';
import { EditStaffProfileForm } from './EditStaffProfileForm';
import { NotificationsProvider } from './NotificationsContext';
import { Avatar } from './dx/Avatar';

interface NavEntry {
  to: string;
  label: string;
  icon: LucideIcon;
}

// Grouped so a long list reads as three short ones.
const staffNavGroups: { label: string; items: NavEntry[] }[] = [
  {
    label: 'Fees',
    items: [
      { to: '/dashboard', label: 'Overview', icon: LayoutGrid },
      { to: '/students', label: 'Students', icon: Users },
      { to: '/classes', label: 'Grades', icon: GraduationCap },
      { to: '/teachers', label: 'Teachers', icon: Users2 },
      { to: '/invoices', label: 'Invoices', icon: FileText },
    ],
  },
  {
    label: 'Communicate',
    items: [
      { to: '/assistant', label: 'Ask Ledgr', icon: Sparkles },
      { to: '/messages', label: 'Messages', icon: MessageCircle },
      { to: '/class-groups', label: 'Class groups', icon: Users2 },
      { to: '/announcements', label: 'Announcements', icon: Megaphone },
      { to: '/guardian-requests', label: 'Parent requests', icon: UserCheck },
    ],
  },
  {
    label: 'Admin',
    items: [
      { to: '/chat-reports', label: 'Chat reports', icon: Flag },
      { to: '/audit-log', label: 'Audit log', icon: ScrollText },
      { to: '/security', label: 'Security', icon: ShieldCheck },
    ],
  },
];

// A teacher account has no fee/invoice data access at all — the only
// thing they're here for is their grades' class groups, so the nav stays
// deliberately narrow rather than showing a wall of pages that would just
// 403 or bounce them straight back out.
const teacherNavGroups: { label: string; items: NavEntry[] }[] = [
  {
    label: 'Chats',
    items: [
      { to: '/class-groups', label: 'Class groups', icon: Users2 },
      { to: '/chats', label: 'Private chats', icon: MessagesSquare },
    ],
  },
];

function CountBadge({ count, tone = 'green', title, onLime }: { count: number; tone?: 'green' | 'amber'; title?: string; onLime?: boolean }) {
  return (
    <span
      title={title}
      className={`pop-in ml-auto min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-bold flex items-center justify-center ${
        onLime ? 'bg-[#0B1203] text-lime' : `text-[#06110B] ${tone === 'amber' ? 'bg-amber' : 'bg-green'}`
      }`}
    >
      {count > 99 ? '99+' : count}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const notif = useUnreadNotifications();
  const isTeacherRole = useAuthStore((st) => st.user?.role === 'TEACHER');
  // What the bell lists besides @mentions. Teachers have no school inbox; only teachers have private chats.
  const bellItems: BellItem[] = isTeacherRole
    ? [
        { key: 'class', label: 'Class group chat', count: notif.unreadClassGroups, to: '/class-groups', icon: Users2 },
        { key: 'direct', label: 'Private chats', count: notif.unreadDirect, to: '/chats', icon: MessagesSquare },
      ]
    : [
        { key: 'school', label: 'Messages from parents', count: notif.unreadMessages, to: '/messages', icon: MessageCircle },
        { key: 'class', label: 'Class group chat', count: notif.unreadClassGroups, to: '/class-groups', icon: Users2 },
      ];
  const bell = (
    <NotificationBell
      total={notif.total}
      items={bellItems}
      unreadMentions={notif.unreadMentions}
      mentions={notif.mentions}
      mentionsLoaded={notif.mentionsLoaded}
      mentionsFailed={notif.mentionsFailed}
      onOpen={notif.loadMentions}
      onMarkSeen={notif.markSeen}
    />
  );
  const { user, logout } = useAuthStore();
  const isTeacher = user?.role === 'TEACHER';
  // Chat reports are for the school admin only (the bursar doesn't see them).
  const navGroups = (isTeacher ? teacherNavGroups : staffNavGroups).map((g) => ({
    ...g,
    items: g.items.filter((i) => i.to !== '/chat-reports' || user?.role === 'SCHOOL_ADMIN'),
  })).filter((g) => g.items.length > 0);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [editProfileOpen, setEditProfileOpen] = useState(false);
  const [collapsed, toggleCollapsed] = useSidebarCollapsed('ledgr.sidebar.staff');
  const searchRef = useRef<HTMLInputElement>(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Ctrl/Cmd+K jumps to the student search (staff only; teachers have no student list).
  useEffect(() => {
    if (isTeacher) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isTeacher]);

  function submitSearch(e: FormEvent, onClose?: () => void) {
    e.preventDefault();
    const q = searchTerm.trim();
    if (!q) return;
    navigate(`/students?q=${encodeURIComponent(q)}`);
    setSearchTerm('');
    searchRef.current?.blur();
    onClose?.();
  }

  // "Fees / Overview" — which group and page the current route belongs to.
  const crumb = (() => {
    for (const g of navGroups) {
      for (const i of g.items) {
        if (location.pathname === i.to || location.pathname.startsWith(`${i.to}/`)) return { group: g.label, page: i.label };
      }
    }
    return null;
  })();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const displayName = user?.full_name || user?.email || '';
  const roleLabel = user?.role.toLowerCase().replace('_', ' ') ?? '';

  /** One panel for the desktop rail (can retract) and the phone drawer (always open). */
  const renderSidebar = (c: boolean, onClose?: () => void) => (
    <>
      <div className={`flex items-center pt-5 pb-3 ${c ? 'justify-center px-3' : 'gap-2 px-4'}`}>
        <button
          onClick={() => {
            setEditProfileOpen(true);
            onClose?.();
          }}
          title={c ? displayName : 'Edit your details'}
          className={`group flex items-center min-w-0 rounded-xl hover:bg-white/[0.05] transition-colors ${c ? 'p-1' : 'flex-1 gap-3 p-1.5 pr-3'}`}
        >
          <Avatar name={displayName || '?'} size={36} />
          {!c && (
            <>
              <span className="min-w-0 flex-1 text-left">
                <span className="block text-sm font-medium truncate text-ink-900">{displayName}</span>
                <span className="block text-xs text-ink-400 capitalize">{roleLabel}</span>
              </span>
              <Pencil className="w-3.5 h-3.5 text-ink-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" strokeWidth={2} />
            </>
          )}
        </button>
        {onClose && (
          <button onClick={onClose} aria-label="Close menu" className="ml-auto text-ink-600 hover:text-ink-900 md:hidden">
            <X className="w-5 h-5" strokeWidth={2} />
          </button>
        )}
      </div>

      {!isTeacher &&
        (c ? (
          <button
            onClick={() => navigate('/students')}
            title="Search students"
            aria-label="Search students"
            className="mx-auto mb-3 w-10 h-10 rounded-xl bg-white/[0.05] text-ink-600 hover:text-ink-900 flex items-center justify-center transition-colors"
          >
            <Search className="w-[18px] h-[18px]" strokeWidth={1.75} />
          </button>
        ) : (
          <form onSubmit={(e) => submitSearch(e, onClose)} className="px-4 pb-3" role="search">
            <label className="relative block">
              <span className="sr-only">Search students</span>
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400" strokeWidth={2} />
              <input
                ref={onClose ? undefined : searchRef}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search students…"
                className="w-full rounded-xl bg-white/[0.05] border border-white/[0.06] pl-9 pr-12 py-2 text-sm text-ink-900 placeholder:text-ink-400 focus:outline-none focus:border-lime/50 transition-colors"
              />
              <kbd className="hidden md:block absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-ink-400 border border-white/10 rounded px-1.5 py-0.5">⌘K</kbd>
            </label>
          </form>
        ))}

      <nav className="flex-1 px-3 flex flex-col gap-5 overflow-y-auto overflow-x-hidden pb-4">
        {navGroups.map((group) => (
          <div key={group.label} className="flex flex-col gap-0.5">
            {c ? (
              <div className="mx-3 mb-1 h-px bg-white/[0.07]" aria-hidden="true" />
            ) : (
              <p className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">{group.label}</p>
            )}
            {group.items.map(({ to, label, icon: Icon }) => {
              const badge =
                to === '/chat-reports' ? { n: notif.openChatReports, tone: 'amber' as const, title: undefined }
                : to === '/chats' ? { n: notif.unreadDirect, tone: 'green' as const, title: undefined }
                : to === '/class-groups' ? { n: notif.unreadClassGroups, tone: (notif.unreadMentions > 0 ? 'amber' : 'green') as 'amber' | 'green', title: notif.unreadMentions > 0 ? 'Someone mentioned you' : 'Unread messages' }
                : { n: 0, tone: 'green' as const, title: undefined };
              return (
                <NavLink
                  key={to}
                  to={to}
                  title={c ? label : undefined}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `flex items-center rounded-xl py-2.5 text-sm transition-colors ${c ? 'justify-center px-0' : 'px-3'} ${
                      isActive ? 'bg-lime text-[#0B1203] font-semibold' : 'font-medium text-ink-600 hover:text-ink-900 hover:bg-white/[0.05]'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span className="relative w-5 h-5 flex items-center justify-center shrink-0">
                        <Icon className="w-[18px] h-[18px]" strokeWidth={isActive ? 2.25 : 1.75} />
                        {c && badge.n > 0 && (
                          <span className={`pop-in absolute -top-1.5 -right-1.5 w-2.5 h-2.5 rounded-full ring-2 ${isActive ? 'ring-lime' : 'ring-[#0A0C16]'} ${badge.tone === 'amber' ? 'bg-amber' : 'bg-green'}`} />
                        )}
                      </span>
                      <span className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${c ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>{label}</span>
                      {!c && badge.n > 0 && <CountBadge count={badge.n} tone={badge.tone} title={badge.title} onLime={isActive} />}
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="px-3 py-3 border-t border-white/[0.07] flex flex-col gap-1">
        {/* Retract / expand — desktop only (the phone drawer just closes). */}
        {!onClose && (
          <button
            onClick={toggleCollapsed}
            aria-label={c ? 'Expand side panel' : 'Retract side panel'}
            title={c ? 'Expand' : 'Retract'}
            className={`flex items-center rounded-xl py-2.5 text-sm font-medium text-ink-600 hover:bg-white/[0.05] hover:text-ink-900 transition-colors ${c ? 'justify-center px-0' : 'px-3'}`}
          >
            <span className="w-5 h-5 flex items-center justify-center shrink-0">
              {c ? <PanelLeftOpen className="w-[18px] h-[18px]" strokeWidth={1.75} /> : <PanelLeftClose className="w-[18px] h-[18px]" strokeWidth={1.75} />}
            </span>
            <span className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${c ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>Retract</span>
          </button>
        )}
        <button
          onClick={handleLogout}
          title={c ? 'Sign out' : undefined}
          className={`flex items-center rounded-xl py-2.5 text-sm font-medium text-ink-600 hover:bg-white/[0.05] hover:text-ink-900 transition-colors ${c ? 'justify-center px-0' : 'px-3'}`}
        >
          <span className="w-5 h-5 flex items-center justify-center shrink-0">
            <LogOut className="w-[18px] h-[18px]" strokeWidth={2} />
          </span>
          <span className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${c ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>Sign out</span>
        </button>
        <div className={`flex items-center pt-3 ${c ? 'justify-center' : 'gap-2.5 px-3'}`}>
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shrink-0">
            <BookOpen className="w-3.5 h-3.5 text-[#06110B]" strokeWidth={2.25} />
          </div>
          {!c && <span className="font-display text-base font-semibold tracking-tight text-ink-900">Ledgr</span>}
        </div>
      </div>
    </>
  );

  // Phone dock: the few screens used all day, the assistant raised in the
  // middle, and a Menu tab that opens the full list.
  const menuItem: BottomNavItem = { label: 'Menu', icon: Menu, onClick: () => setMobileNavOpen(true) };
  const bottomItems: BottomNavItem[] = isTeacher
    ? [
        { label: 'Groups', to: '/class-groups', icon: Users2, badge: notif.unreadClassGroups, badgeTone: notif.unreadMentions > 0 ? 'amber' : 'green' },
        { label: 'Chats', to: '/chats', icon: MessagesSquare, badge: notif.unreadDirect },
        menuItem,
      ]
    : [
        { label: 'Overview', to: '/dashboard', icon: LayoutGrid },
        { label: 'Students', to: '/students', icon: Users },
        { label: 'Ask', to: '/assistant', icon: Sparkles, center: true },
        { label: 'Invoices', to: '/invoices', icon: FileText },
        menuItem,
      ];

  return (
    <NotificationsProvider value={notif}>
    <div className="min-h-dvh flex relative">
      {/* Phone top bar — the fixed sidebar only fits from md up. */}
      <div className="md:hidden fixed top-0 inset-x-0 z-30 flex items-center justify-between px-4 py-3 glass-bar">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shadow-[0_6px_18px_-4px_rgba(57,255,136,0.55)]">
            <BookOpen className="w-4 h-4 text-[#06110B]" strokeWidth={2.25} />
          </div>
          <span className="font-display text-base font-semibold tracking-tight">Ledgr</span>
        </div>
        <div className="flex items-center gap-2">
          <BackButton className="!px-2.5 !py-1" />
          {bell}
        </div>
      </div>

      {mobileNavOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="modal-backdrop-in absolute inset-0 bg-ink-950/60" onClick={() => setMobileNavOpen(false)} aria-hidden="true" />
          <aside className="drawer-in relative w-72 max-w-[85vw] bg-paper border-r border-white/10 flex flex-col h-full shadow-[20px_0_50px_-10px_rgba(0,0,0,0.8)]">
            {renderSidebar(false, () => setMobileNavOpen(false))}
          </aside>
        </div>
      )}

      <aside
        className={`hidden md:flex md:flex-col sticky top-0 h-dvh self-start shrink-0 z-20 border-r border-white/[0.07] bg-paper/55 backdrop-blur-xl overflow-x-hidden transition-[width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          collapsed ? 'w-[72px]' : 'w-64'
        }`}
      >
        {renderSidebar(collapsed)}
      </aside>

      <main className="flex-1 min-w-0 relative z-10 pt-14 md:pt-0 pb-28 md:pb-0">
        {/* Top-right actions: go back + notifications */}
        <div className="hidden md:flex items-center justify-between gap-4 px-6 xl:px-8 pt-5">
          <div className="flex items-center gap-3 min-w-0">
            <BackButton />
            {crumb && (
              <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm min-w-0">
                <span className="text-ink-400">{crumb.group}</span>
                <span className="text-ink-400" aria-hidden="true">/</span>
                <span className="text-ink-900 font-medium truncate">{crumb.page}</span>
              </nav>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => window.location.reload()}
              aria-label="Refresh"
              title="Refresh"
              className="w-10 h-10 rounded-full bg-dx border border-white/[0.08] flex items-center justify-center text-ink-600 hover:text-ink-900 transition-colors"
            >
              <RefreshCw className="w-4 h-4" strokeWidth={1.75} />
            </button>
            {bell}
          </div>
        </div>
        <div key={location.pathname} className="page-enter">
          {children}
        </div>
      </main>

      <BottomNav items={bottomItems} />
      {!isTeacher && <AssistantFab to="/assistant" />}

      {editProfileOpen && (
        <Modal title="Edit your details" onClose={() => setEditProfileOpen(false)}>
          <EditStaffProfileForm onSuccess={() => setEditProfileOpen(false)} onCancel={() => setEditProfileOpen(false)} />
        </Modal>
      )}
    </div>
    </NotificationsProvider>
  );
}
