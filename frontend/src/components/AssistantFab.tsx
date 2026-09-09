import { Link, useLocation } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

export function AssistantFab({ to }: { to: string }) {
  const location = useLocation();

  // No point floating a button to the page you're already on.
  if (location.pathname === to) return null;

  return (
    <Link
      to={to}
      aria-label="Ask Ledgr"
      title="Ask Ledgr"
      className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-ink-900 text-paper shadow-lg flex items-center justify-center hover:bg-ink-800 transition-colors"
    >
      <Sparkles className="w-6 h-6" strokeWidth={1.75} />
    </Link>
  );
}
