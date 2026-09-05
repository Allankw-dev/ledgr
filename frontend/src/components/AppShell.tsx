import { type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { BookOpen, LayoutGrid, Users, FileText, ShieldCheck, UserCheck, LogOut, Sparkles, Megaphone } from 'lucide-react';
import { useAuthStore } from '../store/authStore';

const navItems = [
  { to: '/dashboard', label: 'Overview', icon: LayoutGrid },
  { to: '/students', label: 'Students', icon: Users },
  { to: '/invoices', label: 'Invoices', icon: FileText },
  { to: '/assistant', label: 'Ask Ledgr', icon: Sparkles },
  { to: '/announcements', label: 'Announcements', icon: Megaphone },
  { to: '/guardian-requests', label: 'Parent requests', icon: UserCheck },
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
    <div className="min-h-screen flex bg-paper">
      <aside className="w-64 bg-ink-900 text-paper flex flex-col shrink-0">
        <div className="flex items-center gap-2.5 px-6 py-6">
          <div className="w-8 h-8 rounded-md bg-white/10 flex items-center justify-center">
            <BookOpen className="w-4.5 h-4.5" strokeWidth={2} />
          </div>
          <span className="font-display text-lg font-medium">Ledgr</span>
        </div>

        <nav className="flex-1 px-3 flex flex-col gap-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive ? 'bg-white/10 text-white' : 'text-ink-200 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <Icon className="w-4.5 h-4.5" strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 py-4 border-t border-white/10">
          <div className="px-3 py-2 mb-1">
            <p className="text-sm font-medium truncate">{user?.full_name || user?.email}</p>
            <p className="text-xs text-ink-400 capitalize">{user?.role.toLowerCase().replace('_', ' ')}</p>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-ink-200 hover:bg-white/5 hover:text-white transition-colors"
          >
            <LogOut className="w-4.5 h-4.5" strokeWidth={2} />
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0">{children}</main>
    </div>
  );
}
