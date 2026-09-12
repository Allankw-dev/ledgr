import { type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { BookOpen, LogOut } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { AssistantFab } from './AssistantFab';
import { useUnreadNotifications } from '../hooks/useUnreadNotifications';

const navItems = [
  { to: '/parent/dashboard', label: 'Dashboard', badgeKey: 'unreadMessages' as const },
  { to: '/parent/invoices', label: 'Invoices' },
  { to: '/parent/receipts', label: 'Receipts' },
  { to: '/parent/class-group', label: 'Class group', badgeKey: 'unreadClassGroups' as const },
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
  const { user, logout } = useAuthStore();
  const { unreadMessages, unreadClassGroups } = useUnreadNotifications();
  const badgeCounts = { unreadMessages, unreadClassGroups };

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
          {navItems.map(({ to, label, badgeKey }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `shrink-0 px-3 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center ${
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
      </header>
      <main className="max-w-3xl mx-auto px-6 py-8 relative z-10">{children}</main>
      <AssistantFab to="/parent/assistant" />
    </div>
  );
}
