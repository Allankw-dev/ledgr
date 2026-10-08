import { useState, type ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { BookOpen, LayoutGrid, Users, FileText, ShieldCheck, UserCheck, LogOut, Sparkles, Megaphone, ScrollText, MessageCircle, GraduationCap, Users2, Menu, X, MessagesSquare, Flag, Pencil, PanelLeftClose, PanelLeftOpen, type LucideIcon } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';
import { BackButton } from './BackButton';
import { NotificationBell } from './NotificationBell';
import { BottomNav, type BottomNavItem } from './BottomNav';
import { useUnreadNotifications } from '../hooks/useUnreadNotifications';
import { useSidebarCollapsed } from '../hooks/useSidebarCollapsed';
import { Modal } from './ui/Modal';
import { EditStaffProfileForm } from './EditStaffProfileForm';

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

function CountBadge({ count, tone = 'green', title }: { count: number; tone?: 'green' | 'amber'; title?: string }) {
  return (
    <span
      title={title}
      className={`pop-in ml-auto min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-bold flex items-center justify-center text-[#06110B] ${tone === 'amber' ? 'bg-amber' : 'bg-green'}`}
    >
      {count > 99 ? '99+' : count}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const notif = useUnreadNotifications();
  const bell = (
    <NotificationBell
      total={notif.total}
      counts={{ messages: notif.unreadMessages, classGroups: notif.unreadClassGroups, direct: notif.unreadDirect, chatReports: notif.openChatReports }}
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

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const displayName = user?.full_name || user?.email || '';
  const initial = displayName.trim().charAt(0).toUpperCase() || '?';

  /** One panel for the desktop rail (can retract) and the phone drawer (always open). */
  const renderSidebar = (c: boolean, onClose?: () => void) => (
    <>
      <div className={`flex items-center py-6 mb-1 ${c ? 'justify-center px-3' : 'gap-2.5 px-6'}`}>
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shrink-0 shadow-[0_6px_18px_-4px_rgba(57,255,136,0.55)]">
          <BookOpen className="w-[18px] h-[18px] text-[#06110B]" strokeWidth={2.25} />
        </div>
        {!c && <span className="font-display text-xl font-semibold tracking-tight">Ledgr</span>}
        {onClose && (
          <button onClick={onClose} aria-label="Close menu" className="ml-auto text-ink-600 hover:text-ink-900 md:hidden">
            <X className="w-5 h-5" strokeWidth={2} />
          </button>
        )}
      </div>

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
                        {c && badge.n > 0 && (
                          <span className={`pop-in absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full ring-2 ring-[#0A0C16] ${badge.tone === 'amber' ? 'bg-amber' : 'bg-green'}`} />
                        )}
                      </span>
                      <span className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${c ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>{label}</span>
                      {!c && badge.n > 0 && <CountBadge count={badge.n} tone={badge.tone} title={badge.title} />}
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-white/[0.07] flex flex-col gap-1">
        {/* Retract / expand — desktop only (the phone drawer just closes). */}
        {!onClose && (
          <button
            onClick={toggleCollapsed}
            aria-label={c ? 'Expand side panel' : 'Retract side panel'}
            title={c ? 'Expand' : 'Retract'}
            className="flex items-center px-2 py-2 rounded-xl text-sm font-medium text-ink-600 hover:bg-ink-100/70 hover:text-ink-900 transition-colors"
          >
            <span className="w-8 h-8 rounded-lg bg-ink-100/80 flex items-center justify-center shrink-0">
              {c ? <PanelLeftOpen className="w-[18px] h-[18px]" strokeWidth={1.75} /> : <PanelLeftClose className="w-[18px] h-[18px]" strokeWidth={1.75} />}
            </span>
            <span className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${c ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>Retract</span>
          </button>
        )}
        <button
          onClick={() => {
            setEditProfileOpen(true);
            onClose?.();
          }}
          title={c ? displayName : undefined}
          className="w-full flex items-center px-2 py-2 rounded-xl text-left hover:bg-ink-100/70 transition-colors group"
        >
          <span className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] text-sm font-bold flex items-center justify-center shrink-0">{initial}</span>
          <span className={`min-w-0 flex-1 overflow-hidden transition-all duration-300 ${c ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>
            <span className="block text-sm font-medium truncate text-ink-900">{displayName}</span>
            <span className="block text-xs text-ink-400 capitalize">{user?.role.toLowerCase().replace('_', ' ')}</span>
          </span>
          {!c && <Pencil className="w-3.5 h-3.5 text-ink-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" strokeWidth={2} />}
        </button>
        <button
          onClick={handleLogout}
          title={c ? 'Sign out' : undefined}
          className="w-full flex items-center px-2 py-2 rounded-xl text-sm font-medium text-ink-600 hover:bg-ink-100/70 hover:text-ink-900 transition-colors"
        >
          <span className="w-8 h-8 flex items-center justify-center shrink-0">
            <LogOut className="w-[18px] h-[18px]" strokeWidth={2} />
          </span>
          <span className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${c ? 'max-w-0 pl-0 opacity-0' : 'max-w-[11rem] pl-3 opacity-100'}`}>Sign out</span>
        </button>
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
        <div className="hidden md:flex items-center justify-end gap-2 px-8 pt-4">
          <BackButton />
          {bell}
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
  );
}
