import { type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { BookOpen, LogOut } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';

const navItems = [
  { to: '/parent/dashboard', label: 'Dashboard' },
  { to: '/parent/invoices', label: 'Invoices' },
  { to: '/parent/receipts', label: 'Receipts' },
  { to: '/parent/assistant', label: 'Assistant' },
  { to: '/parent/profile', label: 'Profile' },
];

export function ParentShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div className="min-h-screen bg-paper relative">
      <div className="glow-violet" style={{ top: '-260px', left: '50%', right: 'auto', transform: 'translateX(-50%)', width: '900px', height: '620px' }} />

      <header className="relative z-10">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-[#06110B]" strokeWidth={2} />
            </div>
            <span className="font-display text-lg font-semibold">Ledgr</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-ink-600 hidden sm:inline">{user?.full_name || user?.email}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-sm text-ink-600 hover:text-ink-900 transition-colors"
            >
              <LogOut className="w-4 h-4" strokeWidth={2} />
              Sign out
            </button>
          </div>
        </div>
        <nav className="max-w-3xl mx-auto px-6 flex gap-1 overflow-x-auto border-b border-ink-200">
          {navItems.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `shrink-0 px-3 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  isActive
                    ? 'border-emerald-700 text-ink-900'
                    : 'border-transparent text-ink-600 hover:text-ink-900'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="max-w-3xl mx-auto px-6 py-8 relative z-10">{children}</main>
      <AssistantFab to="/parent/assistant" />
    </div>
  );
}
