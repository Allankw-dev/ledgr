import { Link, useLocation } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

// Screens where a floating button would sit on top of something the person is
// actively using (the message box and its send button).
const HIDDEN_ON = ['/parent/class-group', '/parent/chats', '/class-groups', '/chats'];

/**
 * Floating "Ask Ledgr" button. Desktop only: on phones it covered pay buttons,
 * table actions and the chat composer, and the assistant is already one tap
 * away in the navigation (a sparkle icon in the header on the parent portal,
 * "Ask Ledgr" in the staff menu).
 */
export function AssistantFab({ to }: { to: string }) {
  const location = useLocation();

  // No point floating a button to the page you're already on.
  if (location.pathname === to) return null;
  if (HIDDEN_ON.some((p) => location.pathname.startsWith(p))) return null;

  return (
    <Link
      to={to}
      aria-label="Ask Ledgr"
      title="Ask Ledgr"
      className="fab-neu fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-gradient-to-br from-emerald-700 to-cyan hidden md:flex items-center justify-center"
    >
      <Sparkles className="w-6 h-6 text-[#06110B]" strokeWidth={1.75} />
    </Link>
  );
}
