import { ArrowLeft } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const PUBLIC_PATHS = ['/', '/login', '/signup'];

// Each role's landing page — teachers land in their class groups, parents on their dashboard.
function homeFor(role: string | undefined) {
  if (role === 'PARENT') return '/parent/dashboard';
  if (role === 'TEACHER') return '/class-groups';
  return '/dashboard';
}

/**
 * "Go back" button for the top-right of every signed-in page. Goes to the
 * previous page in the browser history; if there isn't one (the page was
 * opened directly or in a new tab) it goes to the person's home page instead
 * of doing nothing. Hidden on the home pages themselves.
 */
export function BackButton({ className = '' }: { className?: string }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const role = useAuthStore((s) => s.user?.role);

  const home = homeFor(role);
  if (PUBLIC_PATHS.includes(pathname) || pathname === home) return null;

  function goBack() {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) navigate(-1);
    else navigate(home, { replace: true });
  }

  return (
    <button
      type="button"
      onClick={goBack}
      aria-label="Go back"
      className={`inline-flex items-center gap-1.5 rounded-full border border-ink-200 bg-panel/80 backdrop-blur-sm px-3.5 py-1.5 text-sm font-medium text-ink-700 hover:text-ink-900 hover:border-ink-600 hover:bg-ink-100 transition-colors ${className}`}
    >
      <ArrowLeft className="w-4 h-4" strokeWidth={2} />
      Back
    </button>
  );
}
