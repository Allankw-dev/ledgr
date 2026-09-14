import { useEffect, useState } from 'react';
import { Fingerprint, Trash2, Plus } from 'lucide-react';
import { Button } from './ui/Button';
import {
  listWebAuthnCredentials,
  getRegisterOptions,
  verifyRegistration,
  deleteWebAuthnCredential,
  type WebAuthnCredentialInfo,
} from '../api/webauthn';
import { isPlatformAuthenticatorAvailable, performRegistration } from '../lib/webauthnBrowser';

function guessDeviceName(): string {
  const ua = navigator.userAgent;
  const platform = /iPhone|iPad/.test(ua) ? 'iPhone/iPad' : /Android/.test(ua) ? 'Android' : /Mac/.test(ua) ? 'Mac' : /Win/.test(ua) ? 'Windows' : 'this device';
  const browser = /Chrome/.test(ua) ? 'Chrome' : /Safari/.test(ua) ? 'Safari' : /Firefox/.test(ua) ? 'Firefox' : /Edg/.test(ua) ? 'Edge' : '';
  return browser ? `${browser} on ${platform}` : platform;
}

export function FingerprintSettings() {
  const [available, setAvailable] = useState(false);
  const [credentials, setCredentials] = useState<WebAuthnCredentialInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function refetch() {
    listWebAuthnCredentials()
      .then(setCredentials)
      .catch(() => setError('Could not load your registered fingerprints.'))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    isPlatformAuthenticatorAvailable().then(setAvailable);
    refetch();
  }, []);

  async function handleEnroll() {
    setError(null);
    setEnrolling(true);
    try {
      const { options, challenge_id } = await getRegisterOptions();
      const credential = await performRegistration(options);
      await verifyRegistration(challenge_id, credential, guessDeviceName());
      refetch();
    } catch (err: unknown) {
      const name = (err as { name?: string })?.name;
      if (name !== 'NotAllowedError') {
        setError("Couldn't set up fingerprint sign-in on this device. Try again.");
      }
    } finally {
      setEnrolling(false);
    }
  }

  async function handleRemove(id: string) {
    if (!window.confirm('Remove this fingerprint? You\'ll need your password to sign in from that device afterward.')) return;
    try {
      await deleteWebAuthnCredential(id);
      refetch();
    } catch {
      setError('Could not remove this fingerprint. Try again.');
    }
  }

  if (!available && !loading && credentials.length === 0) {
    // No point showing the section at all if this device can't enroll one
    // and none exist yet — nothing here would be actionable.
    return null;
  }

  return (
    <div className="bg-panel border border-ink-200 rounded-lg p-6">
      <div className="flex items-center gap-2 mb-1">
        <Fingerprint className="w-5 h-5 text-ink-900" strokeWidth={1.75} />
        <h2 className="font-display text-lg text-ink-900 font-medium">Fingerprint sign-in</h2>
      </div>
      <p className="text-sm text-ink-600 mb-4">
        Sign in with your device's fingerprint, Face ID, or Windows Hello instead of typing your password.
      </p>

      {error && (
        <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2 mb-4">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-ink-600">Loading…</p>
      ) : (
        <>
          {credentials.length > 0 && (
            <div className="flex flex-col gap-2 mb-4">
              {credentials.map((c) => (
                <div key={c.id} className="flex items-center justify-between px-4 py-3 bg-ink-100 rounded-md">
                  <div>
                    <p className="text-sm font-medium text-ink-900">{c.device_name || 'Unnamed device'}</p>
                    <p className="text-xs text-ink-400">
                      Added {new Date(c.created_at).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' })}
                      {c.last_used_at && ` · last used ${new Date(c.last_used_at).toLocaleDateString('en-KE', { day: 'numeric', month: 'short' })}`}
                    </p>
                  </div>
                  <button
                    onClick={() => handleRemove(c.id)}
                    className="text-ink-400 hover:text-clay-700 transition-colors"
                    aria-label="Remove this fingerprint"
                  >
                    <Trash2 className="w-4 h-4" strokeWidth={2} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {available && (
            <Button variant="secondary" onClick={handleEnroll} disabled={enrolling} className="flex items-center gap-2">
              {enrolling ? <span className="orbit-spinner" /> : <Plus className="w-4 h-4" strokeWidth={2} />}
              {enrolling ? 'Waiting for fingerprint…' : 'Add this device'}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
