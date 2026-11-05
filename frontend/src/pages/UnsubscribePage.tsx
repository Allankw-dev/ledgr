import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { resubscribeWithToken, unsubscribeWithToken } from '../api/privacy';
import { Button } from '../components/ui/Button';
import { SiteFooter } from '../components/SiteFooter';

type Status = 'ask' | 'working' | 'done' | 'undone' | 'error';

/**
 * Opened from the link at the bottom of a fee reminder or announcement email. It asks for one click to confirm
 * (so an email scanner that merely opens the link can't unsubscribe anyone), then switches optional email off.
 */
export function UnsubscribePage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [status, setStatus] = useState<Status>(token ? 'ask' : 'error');

  async function run(action: 'unsub' | 'resub') {
    setStatus('working');
    try {
      if (action === 'unsub') await unsubscribeWithToken(token);
      else await resubscribeWithToken(token);
      setStatus(action === 'unsub' ? 'done' : 'undone');
    } catch {
      setStatus('error');
    }
  }

  return (
    <div className="min-h-dvh flex flex-col">
      <main id="main-content" className="flex-1 flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-md rounded-xl border border-ink-200 bg-panel p-6 text-center">
          <h1 className="font-display text-2xl text-ink-900 font-medium mb-3">Email preferences</h1>
          {status === 'ask' && (
            <>
              <p className="text-sm text-ink-700 mb-5">Stop fee reminders and school announcements by email?</p>
              <Button type="button" onClick={() => void run('unsub')}>Yes, unsubscribe me</Button>
              <p className="text-xs text-ink-600 mt-4">Payment receipts and security emails will still be sent.</p>
            </>
          )}
          {status === 'working' && <p role="status" className="text-sm text-ink-700">One moment…</p>}
          {status === 'done' && (
            <div role="status">
              <p className="text-sm text-ink-900 mb-1">You are unsubscribed.</p>
              <p className="text-sm text-ink-700 mb-5">You will no longer get reminders or announcements by email. Payment receipts and security emails still come through.</p>
              <button type="button" onClick={() => void run('resub')} className="text-sm underline text-ink-700 hover:text-ink-900">
                I clicked this by mistake: turn emails back on
              </button>
            </div>
          )}
          {status === 'undone' && (
            <p role="status" className="text-sm text-ink-900">Emails are back on. You can change this any time in Profile → Privacy &amp; data.</p>
          )}
          {status === 'error' && (
            <div role="alert">
              <p className="text-sm text-ink-900 mb-2">This link is invalid or has expired.</p>
              <p className="text-sm text-ink-700">
                <Link to="/login" className="underline">Sign in</Link> and open Profile → Privacy &amp; data to change your email settings.
              </p>
            </div>
          )}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
