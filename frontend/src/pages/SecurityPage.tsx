import { useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { ShieldCheck, ShieldOff, Copy, Check } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { get2FAStatus, setup2FA, enable2FA, disable2FA } from '../api/auth';

type Stage = 'loading' | 'disabled' | 'enabled' | 'setting-up';

export function SecurityPage() {
  const [stage, setStage] = useState<Stage>('loading');
  const [setupData, setSetupData] = useState<{ secret: string; provisioning_uri: string } | null>(null);
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showDisableForm, setShowDisableForm] = useState(false);

  useEffect(() => {
    get2FAStatus()
      .then((res) => setStage(res.enabled ? 'enabled' : 'disabled'))
      .catch(() => setStage('disabled'));
  }, []);

  async function startSetup() {
    setError(null);
    try {
      const data = await setup2FA();
      setSetupData(data);
      setStage('setting-up');
    } catch {
      setError('Could not start setup. Try again.');
    }
  }

  async function confirmEnable(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await enable2FA(code);
      setStage('enabled');
      setSetupData(null);
      setCode('');
    } catch {
      setError('Incorrect code. Check your authenticator app and try again.');
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmDisable(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await disable2FA(password);
      setStage('disabled');
      setShowDisableForm(false);
      setPassword('');
    } catch {
      setError('Incorrect password.');
    } finally {
      setSubmitting(false);
    }
  }

  function copySecret() {
    if (!setupData) return;
    navigator.clipboard.writeText(setupData.secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-8 py-8">
        <h1 className="font-display text-2xl text-ink-900 font-medium mb-1">Security</h1>
        <p className="text-sm text-ink-600 mb-8">Protect your account with two-factor authentication.</p>

        {stage === 'loading' && <p className="text-sm text-ink-600">Loading…</p>}

        {stage === 'disabled' && (
          <div className="bg-panel border border-ink-200 rounded-lg p-6">
            <div className="flex items-start gap-3 mb-4">
              <ShieldOff className="w-5 h-5 text-ink-400 mt-0.5" strokeWidth={1.75} />
              <div>
                <h2 className="font-display text-base text-ink-900 font-medium">
                  Two-factor authentication is off
                </h2>
                <p className="text-sm text-ink-600 mt-1">
                  Add an extra layer of protection — after your password, you'll also need a code from an
                  authenticator app (like Google Authenticator or Authy) to sign in.
                </p>
              </div>
            </div>
            <Button onClick={startSetup}>Set up two-factor authentication</Button>
          </div>
        )}

        {stage === 'setting-up' && setupData && (
          <div className="bg-panel border border-ink-200 rounded-lg p-6">
            <h2 className="font-display text-base text-ink-900 font-medium mb-4">
              Scan this code with your authenticator app
            </h2>

            <div className="flex justify-center bg-panel p-4 border border-ink-200 rounded-lg mb-4 w-fit mx-auto">
              <QRCodeSVG value={setupData.provisioning_uri} size={180} />
            </div>

            <p className="text-xs text-ink-600 text-center mb-2">Can't scan? Enter this code manually:</p>
            <button
              onClick={copySecret}
              className="figure text-sm text-ink-900 bg-ink-100 rounded-md px-3 py-2 mx-auto flex items-center gap-2 mb-6 hover:bg-ink-200 transition-colors"
            >
              {setupData.secret}
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-700" /> : <Copy className="w-3.5 h-3.5" />}
            </button>

            <form onSubmit={confirmEnable} className="flex flex-col gap-4">
              <TextField
                label="Enter the 6-digit code to confirm"
                inputMode="numeric"
                maxLength={6}
                placeholder="000000"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              />
              {error && <p className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">{error}</p>}
              <div className="flex gap-2">
                <Button type="submit" disabled={submitting || code.length !== 6}>
                  {submitting ? 'Verifying…' : 'Enable'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setStage('disabled');
                    setSetupData(null);
                    setError(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        )}

        {stage === 'enabled' && (
          <div className="bg-panel border border-ink-200 rounded-lg p-6">
            <div className="flex items-start gap-3 mb-4">
              <ShieldCheck className="w-5 h-5 text-emerald-700 mt-0.5" strokeWidth={1.75} />
              <div>
                <h2 className="font-display text-base text-ink-900 font-medium">
                  Two-factor authentication is on
                </h2>
                <p className="text-sm text-ink-600 mt-1">
                  You'll need a code from your authenticator app every time you sign in.
                </p>
              </div>
            </div>

            {!showDisableForm ? (
              <Button variant="danger" onClick={() => setShowDisableForm(true)}>
                Disable two-factor authentication
              </Button>
            ) : (
              <form onSubmit={confirmDisable} className="flex flex-col gap-4 max-w-xs">
                <TextField
                  label="Confirm your password to disable"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                />
                {error && <p className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">{error}</p>}
                <div className="flex gap-2">
                  <Button type="submit" variant="danger" disabled={submitting}>
                    {submitting ? 'Disabling…' : 'Confirm disable'}
                  </Button>
                  <Button type="button" variant="secondary" onClick={() => setShowDisableForm(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
