import { useEffect, useRef, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { BookOpen, CheckCircle2 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { confirmEmailChange } from '../api/auth';
import { getErrorMessage } from '../api/client';

// Opened from the link emailed to the NEW address. Public on purpose: it may be
// opened on a different device from the one the parent is signed in on — the
// signed token in the link is the proof, not a session.
export function ConfirmEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [state, setState] = useState<'working' | 'done' | 'error'>(token ? 'working' : 'error');
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(token ? null : 'This link is missing its token. Request the change again from your profile.');
  // The link is single-use, and React StrictMode runs effects twice in dev —
  // guard so the second run doesn't turn a success into a "already used" error.
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    confirmEmailChange(token)
      .then((r) => {
        setEmail(r.email);
        setState('done');
      })
      .catch((err: unknown) => {
        setError(getErrorMessage(err, 'Could not confirm this email change.'));
        setState('error');
      });
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper px-4 relative overflow-hidden">
      <div className="glow-violet" />
      <div className="glow-cyan" />
      <div className="w-full max-w-sm relative z-10">
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-[#06110B]" strokeWidth={2} />
          </div>
          <span className="font-display text-2xl text-ink-900 font-medium">Ledgr</span>
        </div>

        <div className="bg-panel border border-ink-200 rounded-3xl p-8 shadow-[0_0_50px_-16px_rgba(139,108,255,0.25)]">
          {state === 'working' && (
            <div className="flex items-center gap-3 text-sm text-ink-600">
              <span className="orbit-spinner" /> Confirming your new email…
            </div>
          )}
          {state === 'done' && (
            <>
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="w-5 h-5 text-emerald-700" strokeWidth={1.75} />
                <h1 className="font-display text-xl text-ink-900">Email updated</h1>
              </div>
              <p className="text-sm text-ink-600 mb-6">
                You can now sign in with <span className="font-medium text-ink-900">{email}</span>. For your security,
                you've been signed out everywhere.
              </p>
              <Button onClick={() => navigate('/login')}>Go to sign in</Button>
            </>
          )}
          {state === 'error' && (
            <>
              <h1 className="font-display text-xl text-ink-900 mb-2">Couldn't confirm</h1>
              <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2 mb-6">
                {error}
              </p>
              <Button onClick={() => navigate('/login')}>Back to sign in</Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
