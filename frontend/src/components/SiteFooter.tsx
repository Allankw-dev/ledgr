import { Link } from 'react-router-dom';
import { OPERATOR } from '../config/legal';

/** Legal links and the operator's business details. Shown on the sign-in page, the legal pages and inside the app. */
export function SiteFooter({ className = '' }: { className?: string }) {
  const details = [OPERATOR.name, OPERATOR.address, OPERATOR.email].filter(Boolean).join(' · ');
  return (
    <footer className={`w-full px-5 py-5 text-center text-xs text-ink-600 ${className}`}>
      <nav aria-label="Legal" className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
        <Link className="underline underline-offset-2 hover:text-ink-900" to="/privacy">Privacy Policy</Link>
        <Link className="underline underline-offset-2 hover:text-ink-900" to="/terms">Terms of Service</Link>
        <Link className="underline underline-offset-2 hover:text-ink-900" to="/refunds">Refund Policy</Link>
        <Link className="underline underline-offset-2 hover:text-ink-900" to="/cookies">Cookie Policy</Link>
      </nav>
      {details && <p className="mt-2">{details}</p>}
    </footer>
  );
}
