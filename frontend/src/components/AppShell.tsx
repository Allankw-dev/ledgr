import { useState, type ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { BookOpen, LayoutGrid, Users, FileText, ShieldCheck, UserCheck, LogOut, Sparkles, Megaphone, ScrollText, MessageCircle, GraduationCap, Users2, Menu, X, MessagesSquare, Flag, Pencil, type LucideIcon } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';
import { BackButton } from './BackButton';
import { NotificationBell } from './NotificationBell';
import { BottomNav, type BottomNavItem } from './BottomNav';
import { useUnreadNotifications } from '../hooks/useUnreadNotifications';
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
      unreadMentions={notif.unreadMentions}
      mentions={notif.mentions}
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

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const displayName = user?.full_name || user?.email || '';
  const initial = displayName.trim().charAt(0).toUpperCase() || '?';

  const sidebarContent = (
    <>
      <div className="flex items-center gap-2.5 px-6 py-6 mb-1">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shrink-0 shadow-[0_6px_18px_-4px_rgba(57,255,136,0.55)]">
          <BookOpen className="w-[18px] h-[18px] text-[#06110B]" strokeWidth={2.25} />
        </div>
        <span className="font-display text-xl font-semibold tracking-tight">Ledgr</span>
        <button
          onClick={() => setMobileNavOpen(false)}
          aria-label="Close menu"
          className="ml-auto text-ink-600 hover:text-ink-900 md:hidden"
        >
          <X className="w-5 h-5" strokeWidth={2} />
        </button>
      </div>

      <nav className="flex-1 px-3 flex flex-col gap-5 overflow-y-auto pb-4">
        {navGroups.map((group) => (
          <div key={group.label} className="flex flex-col gap-0.5">
            <p className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">{group.label}</p>
            {group.items.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMobileNavOpen(false)}
                className={({ isActive }) =>
                  `side-link flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium ${
                    isActive ? 'text-ink-900' : 'text-ink-600 hover:text-ink-900 hover:bg-ink-100/70'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                        isActive ? 'bg-green/15 text-green' : 'bg-ink-100/80 text-ink-600'
                      }`}
                    >
                      <Icon className="w-[18px] h-[18px]" strokeWidth={isActive ? 2.25 : 1.75} />
                    </span>
                    {label}
                    {to === '/chat-reports' && notif.openChatReports > 0 && <CountBadge count={notif.openChatReports} tone="amber" />}
                    {to === '/chats' && notif.unreadDirect > 0 && <CountBadge count={notif.unreadDirect} />}
                    {to === '/class-groups' && notif.unreadClassGroups > 0 && (
                      <CountBadge
                        count={notif.unreadClassGroups}
                        tone={notif.unreadMentions > 0 ? 'amber' : 'green'}
                        title={notif.unreadMentions > 0 ? 'Someone mentioned you' : 'Unread messages'}
                      />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-white/[0.07]">
        <button
          onClick={() => {
            setEditProfileOpen(true);
            setMobileNavOpen(false);
          }}
          className="w-full flex items-center gap-3 px-3 py-2 mb-1 rounded-xl text-left hover:bg-ink-100/70 transition-colors group"
        >
          <span className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] text-sm font-bold flex items-center justify-center shrink-0">{initial}</span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium truncate text-ink-900">{displayName}</span>
            <span className="block text-xs text-ink-400 capitalize">{user?.role.toLowerCase().replace('_', ' ')}</span>
          </span>
          <Pencil className="w-3.5 h-3.5 text-ink-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" strokeWidth={2} />
        </button>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-ink-600 hover:bg-ink-100/70 hover:text-ink-900 transition-colors"
        >
          <LogOut className="w-[18px] h-[18px]" strokeWidth={2} />
          Sign out
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
          <aside className="relative w-72 max-w-[85vw] bg-paper border-r border-white/10 flex flex-col h-full shadow-[20px_0_50px_-10px_rgba(0,0,0,0.8)]">
            {sidebarContent}
          </aside>
        </div>
      )}

      <aside className="w-64 border-r border-white/[0.07] bg-paper/55 backdrop-blur-xl shrink-0 relative z-10 hidden md:flex md:flex-col sticky top-0 h-dvh self-start">
        {sidebarContent}
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
