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
      className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-gradient-to-br from-emerald-700 to-cyan shadow-[0_8px_28px_-6px_rgba(57,255,136,0.55)] flex items-center justify-center hover:brightness-110 transition-all"
    >
      <Sparkles className="w-6 h-6 text-[#06110B]" strokeWidth={1.75} />
    </Link>
  );
}
