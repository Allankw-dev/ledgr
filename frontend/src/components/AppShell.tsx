import { useState, type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { BookOpen, LayoutGrid, Users, FileText, ShieldCheck, UserCheck, LogOut, Sparkles, Megaphone, ScrollText, MessageCircle, GraduationCap, Users2, Menu, X } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';

const staffNavItems = [
  { to: '/dashboard', label: 'Overview', icon: LayoutGrid },
  { to: '/students', label: 'Students', icon: Users },
  { to: '/classes', label: 'Grades', icon: GraduationCap },
  { to: '/teachers', label: 'Teachers', icon: Users2 },
  { to: '/invoices', label: 'Invoices', icon: FileText },
  { to: '/assistant', label: 'Ask Ledgr', icon: Sparkles },
  { to: '/messages', label: 'Messages', icon: MessageCircle },
  { to: '/class-groups', label: 'Class groups', icon: Users2 },
  { to: '/announcements', label: 'Announcements', icon: Megaphone },
  { to: '/guardian-requests', label: 'Parent requests', icon: UserCheck },
  { to: '/audit-log', label: 'Audit log', icon: ScrollText },
  { to: '/security', label: 'Security', icon: ShieldCheck },
];

// A teacher account has no fee/invoice data access at all — the only
// thing they're here for is their grades' class groups, so the nav stays
// deliberately narrow rather than showing a wall of pages that would just
// 403 or bounce them straight back out.
const teacherNavItems = [{ to: '/class-groups', label: 'Class groups', icon: Users2 }];

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const isTeacher = user?.role === 'TEACHER';
  const navItems = isTeacher ? teacherNavItems : staffNavItems;
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const sidebarContent = (
    <>
      <div className="flex items-center gap-2.5 px-6 py-6 border-b border-ink-200 mb-2">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shrink-0">
          <BookOpen className="w-4.5 h-4.5 text-[#06110B]" strokeWidth={2} />
        </div>
        <span className="font-display text-lg font-semibold">Ledgr</span>
        <button
          onClick={() => setMobileNavOpen(false)}
          aria-label="Close menu"
          className="ml-auto text-ink-600 hover:text-ink-900 md:hidden"
        >
          <X className="w-5 h-5" strokeWidth={2} />
        </button>
      </div>

      <nav className="flex-1 px-3 flex flex-col gap-1 overflow-y-auto">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => setMobileNavOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors border-l-2 ${
                isActive
                  ? 'text-ink-900 border-emerald-700 bg-gradient-to-r from-emerald-100 to-transparent'
                  : 'text-ink-600 border-transparent hover:text-ink-900 hover:bg-ink-100'
              }`
            }
          >
            <Icon className="w-4.5 h-4.5" strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-ink-200">
        <div className="px-3 py-2 mb-1">
          <p className="text-sm font-medium truncate text-ink-900">{user?.full_name || user?.email}</p>
          <p className="text-xs text-ink-400 capitalize">{user?.role.toLowerCase().replace('_', ' ')}</p>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-ink-600 hover:bg-ink-100 hover:text-ink-900 transition-colors"
        >
          <LogOut className="w-4.5 h-4.5" strokeWidth={2} />
          Sign out
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen flex bg-paper relative">
      <div className="glow-violet" />
      <div className="glow-cyan" />

      {/* Mobile top bar — the fixed sidebar only fits from md up, so
         anything narrower gets a hamburger that opens the same nav as a
         slide-over drawer instead. */}
      <div className="md:hidden fixed top-0 inset-x-0 z-30 flex items-center justify-between px-4 py-3 border-b border-ink-200 bg-paper/95 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-[#06110B]" strokeWidth={2} />
          </div>
          <span className="font-display text-base font-semibold">Ledgr</span>
        </div>
        <button
          onClick={() => setMobileNavOpen(true)}
          aria-label="Open menu"
          className="text-ink-900"
        >
          <Menu className="w-6 h-6" strokeWidth={2} />
        </button>
      </div>

      {mobileNavOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-ink-950/50" onClick={() => setMobileNavOpen(false)} aria-hidden="true" />
          <aside className="relative w-72 max-w-[85vw] bg-paper border-r border-ink-200 flex flex-col h-full">
            {sidebarContent}
          </aside>
        </div>
      )}

      <aside className="w-64 border-r border-ink-200 shrink-0 relative z-10 hidden md:flex md:flex-col">
        {sidebarContent}
      </aside>

      <main className="flex-1 min-w-0 relative z-10 pt-14 md:pt-0">{children}</main>
      {!isTeacher && <AssistantFab to="/assistant" />}
    </div>
  );
}
