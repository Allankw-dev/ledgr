import { type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, LogOut } from 'lucide-react';
import { useAuthStore } from '../store/authStore';

export function ParentShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-ink-900 text-paper">
        <div className="max-w-2xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center">
              <BookOpen className="w-4 h-4" strokeWidth={2} />
            </div>
            <span className="font-display text-lg font-medium">Ledgr</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-ink-200 hidden sm:inline">{user?.full_name || user?.email}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-sm text-ink-200 hover:text-white transition-colors"
            >
              <LogOut className="w-4 h-4" strokeWidth={2} />
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
