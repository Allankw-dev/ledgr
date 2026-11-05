import { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Check, Copy, ShieldAlert } from 'lucide-react';
import { DxCard } from './dx/DxCard';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { enable2FA, setup2FA } from '../api/auth';
import { getErrorMessage } from '../api/client';

/**
 * Shown instead of the platform screens until the operator has two-factor sign-in on. The platform routes can switch
 * schools off and change where a school's M-Pesa money goes, so the server refuses an operator without 2FA (403).
 * This is the whole set-up on one card, because the staff Security page needs a school and the operator has none.
 */
export function OperatorTwoFactor({ onEnabled }: { onEnabled: () => void }) {
  const [setup, setSetup] = useState<{ secret: string; provisioning_uri: string } | null>(null);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  async function start() {
    setBusy(true);
    setError('');
    try {
      setSetup(await setup2FA());
    } catch (err) {
      setError(getErrorMessage(err, 'Could not start set-up. Try again.'));
    } finally {
      setBusy(false);
    }
  }

  async function confirm(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await enable2FA(code);
      onEnabled();
    } catch {
      setError('Incorrect code. Check your authenticator app and try again.');
    } finally {
      setBusy(false);
    }
  }

  function copySecret() {
    if (!setup) return;
    void navigator.clipboard.writeText(setup.secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <DxCard className="p-6 max-w-xl">
      <div className="flex items-start gap-3 mb-4">
        <ShieldAlert className="w-5 h-5 text-amber mt-0.5" strokeWidth={1.75} />
        <div>
          <h2 className="font-display text-lg text-ink-900">Turn on two-factor sign-in first</h2>
          <p className="text-sm text-ink-600 mt-1">
            The platform tools can switch schools off and change where a school&apos;s M-Pesa money goes, so they stay locked until
            your account asks for a code from an authenticator app (Google Authenticator, Authy…) as well as your password.
          </p>
        </div>
      </div>

      {!setup && <Button onClick={start} disabled={busy}>{busy ? 'Starting…' : 'Set up two-factor sign-in'}</Button>}

      {setup && (
        <>
          <p className="text-sm text-ink-900 mb-3">Scan this code with your authenticator app:</p>
          <div className="bg-white p-3 rounded-lg w-fit mx-auto mb-3">
            <QRCodeSVG value={setup.provisioning_uri} size={176} />
          </div>
          <p className="text-xs text-ink-600 text-center mb-2">Can&apos;t scan? Enter this code by hand:</p>
          <button
            type="button"
            onClick={copySecret}
            className="figure text-sm text-ink-900 border border-white/10 rounded-md px-3 py-2 mx-auto flex items-center gap-2 mb-5"
            aria-label="Copy the set-up code"
          >
            {setup.secret}
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
          <form onSubmit={confirm} className="flex flex-col gap-3">
            <TextField
              label="6-digit code"
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            />
            <Button type="submit" disabled={busy || code.length !== 6}>{busy ? 'Checking…' : 'Turn on'}</Button>
          </form>
        </>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-coral">{error}</p>}
    </DxCard>
  );
}
