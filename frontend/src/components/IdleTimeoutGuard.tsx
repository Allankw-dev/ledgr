import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

// A finance app left open on a shared school-office computer is a real
// risk — this signs staff/parents out after a period of no activity,
// with a warning window so an actively-reading user isn't cut off mid-task.
const IDLE_MS = 14 * 60 * 1000; // warn after 14 minutes of no activity
const WARNING_MS = 60 * 1000; // 60s to respond before auto sign-out

const ACTIVITY_EVENTS = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart'] as const;

export function IdleTimeoutGuard({ children }: { children: ReactNode }) {
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const [warning, setWarning] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(WARNING_MS / 1000);

  // Refs, not state, for the "are we currently warning" check inside event
  // handlers — event listeners are attached once (see effect below), so a
  // handler reading `warning` directly would see a stale closure and never
  // notice the warning had started.
  const warningRef = useRef(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    warningRef.current = warning;
  }, [warning]);

  const clearTimers = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    if (countdownTimer.current) clearInterval(countdownTimer.current);
  }, []);

  const handleLogout = useCallback(() => {
    clearTimers();
    logout();
    navigate('/login', { replace: true });
  }, [clearTimers, logout, navigate]);

  const startWarningCountdown = useCallback(() => {
    setWarning(true);
    warningRef.current = true;
    setSecondsLeft(WARNING_MS / 1000);
    countdownTimer.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          handleLogout();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  }, [handleLogout]);

  const resetIdleTimer = useCallback(() => {
    if (warningRef.current) return; // once warning is up, only the buttons below can clear it
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(startWarningCountdown, IDLE_MS);
  }, [startWarningCountdown]);

  useEffect(() => {
    resetIdleTimer();
    ACTIVITY_EVENTS.forEach((evt) => window.addEventListener(evt, resetIdleTimer));
    return () => {
      clearTimers();
      ACTIVITY_EVENTS.forEach((evt) => window.removeEventListener(evt, resetIdleTimer));
    };
  }, [resetIdleTimer, clearTimers]);

  function handleStaySignedIn() {
    clearTimers();
    warningRef.current = false;
    setWarning(false);
    idleTimer.current = setTimeout(startWarningCountdown, IDLE_MS);
  }

  return (
    <>
      {children}
      {warning && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-ink-950/50" aria-hidden="true" />
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="idle-title"
            className="relative bg-white rounded-lg border border-ink-200 shadow-lg w-full max-w-sm p-5 text-center"
          >
            <h2 id="idle-title" className="font-display text-lg text-ink-900 font-medium mb-2">
              Still there?
            </h2>
            <p className="text-sm text-ink-600 mb-4">
              You've been inactive. For your account's security, you'll be signed out in{' '}
              <span className="font-medium text-ink-900">{secondsLeft}s</span>.
            </p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={handleLogout}
                className="px-4 py-2 rounded-md text-sm font-medium border border-ink-200 text-ink-700 hover:bg-ink-100"
              >
                Sign out
              </button>
              <button
                onClick={handleStaySignedIn}
                className="px-4 py-2 rounded-md text-sm font-medium bg-ink-900 text-paper hover:bg-ink-800"
              >
                Stay signed in
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
