import { type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { BookOpen, LayoutGrid, Users, FileText, ShieldCheck, UserCheck, LogOut, Sparkles, Megaphone, ScrollText, MessageCircle, GraduationCap } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';

const navItems = [
  { to: '/dashboard', label: 'Overview', icon: LayoutGrid },
  { to: '/students', label: 'Students', icon: Users },
  { to: '/classes', label: 'Grades', icon: GraduationCap },
  { to: '/invoices', label: 'Invoices', icon: FileText },
  { to: '/assistant', label: 'Ask Ledgr', icon: Sparkles },
  { to: '/messages', label: 'Messages', icon: MessageCircle },
  { to: '/announcements', label: 'Announcements', icon: Megaphone },
  { to: '/guardian-requests', label: 'Parent requests', icon: UserCheck },
  { to: '/audit-log', label: 'Audit log', icon: ScrollText },
  { to: '/security', label: 'Security', icon: ShieldCheck },
];

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div className="min-h-screen flex bg-paper relative">
      <div className="glow-violet" />
      <div className="glow-cyan" />

      <aside className="w-64 border-r border-ink-200 flex flex-col shrink-0 relative z-10">
        <div className="flex items-center gap-2.5 px-6 py-6 border-b border-ink-200 mb-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center">
            <BookOpen className="w-4.5 h-4.5 text-[#06110B]" strokeWidth={2} />
          </div>
          <span className="font-display text-lg font-semibold">Ledgr</span>
        </div>

        <nav className="flex-1 px-3 flex flex-col gap-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
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
      </aside>

      <main className="flex-1 min-w-0 relative z-10">{children}</main>
      <AssistantFab to="/assistant" />
    </div>
  );
}
