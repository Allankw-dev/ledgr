import { useState } from 'react';
import { Link } from 'react-router-dom';

const KEY = 'ledgr-notice-ack';

function alreadyAcknowledged(): boolean {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

/**
 * Tells people what Ledgr keeps on their device. Ledgr sets no cookies and has no analytics or advertising, so
 * nothing here needs a consent choice: this is a notice with one button, not a fake "accept all". If tracking is
 * ever added, replace this with a real accept/decline banner that blocks the tracker until the person agrees.
 */
export function CookieNotice() {
  const [visible, setVisible] = useState(() => !alreadyAcknowledged());
  if (!visible) return null;

  function dismiss() {
    try {
      localStorage.setItem(KEY, '1');
    } catch {
      /* private mode: it will simply show again next visit */
    }
    setVisible(false);
  }

  return (
    <div
      role="region"
      aria-label="Cookie and storage notice"
      className="fixed inset-x-3 bottom-3 z-50 mx-auto max-w-xl rounded-xl border border-ink-200 bg-ink-100 p-4 shadow-lg sm:bottom-4"
    >
      <p className="text-sm text-ink-700 leading-relaxed">
        Ledgr uses no advertising or tracking cookies. It keeps your sign-in session and a few display settings on this device so the app works.{' '}
        <Link to="/cookies" className="underline text-ink-900">Cookie Policy</Link>
        {' · '}
        <Link to="/privacy" className="underline text-ink-900">Privacy Policy</Link>
      </p>
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={dismiss}
          className="rounded-lg bg-green px-4 py-2 text-sm font-medium text-ink-950 hover:opacity-90"
        >
          OK, got it
        </button>
      </div>
    </div>
  );
}
