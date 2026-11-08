import { useCallback, useEffect, useState } from 'react';
import {
  getSchoolMpesa,
  registerSchoolMpesaUrls,
  removeSchoolMpesa,
  rotateSchoolMpesaAddress,
  saveSchoolMpesa,
  setSchoolMpesaMode,
  testSchoolMpesa,
  type MpesaAccountStatus,
  type MpesaActionResult,
  type MpesaEnvironment,
  type MpesaMode,
} from '../api/platformMpesa';
import { getErrorMessage } from '../api/client';

const FIELD = 'mt-1 w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-ink-900';
const BTN = 'rounded-full border border-white/[0.1] px-3 py-1.5 text-xs text-ink-900 hover:border-lime/50 disabled:opacity-40 transition-colors';

const MODE_LABEL: Record<MpesaMode, string> = {
  OFF: 'Off',
  GLOBAL: 'Server-wide paybill',
  OWN: "This school's own paybill",
};

const MODE_HELP: Record<MpesaMode, string> = {
  OFF: 'Parents are not offered "Pay with M-Pesa". Nothing can be sent to anyone\'s paybill.',
  GLOBAL: "Parents pay into the one paybill set on the server (the original single-paybill setup).",
  OWN: "Parents pay into this school's own paybill, using the details saved below.",
};

function when(iso: string | null) {
  return iso ? new Date(iso).toLocaleString('en-KE', { dateStyle: 'medium', timeStyle: 'short' }) : 'not yet';
}

/**
 * The platform operator's panel for ONE school's M-Pesa. The three secrets are write-only: the inputs start empty,
 * are cleared after every save, and the server never returns them, so nothing here can show them back.
 */
export function MpesaSetupPanel({ schoolId, schoolName }: { schoolId: string; schoolName: string }) {
  const [status, setStatus] = useState<MpesaAccountStatus | null>(null);
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  const [environment, setEnvironment] = useState<MpesaEnvironment>('SANDBOX');
  const [shortcode, setShortcode] = useState('');
  const [consumerKey, setConsumerKey] = useState('');
  const [consumerSecret, setConsumerSecret] = useState('');
  const [passkey, setPasskey] = useState('');

  const adopt = useCallback((s: MpesaAccountStatus) => {
    setStatus(s);
    if (s.has_account) {
      setEnvironment(s.environment ?? 'SANDBOX');
      setShortcode(s.shortcode ?? '');
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getSchoolMpesa(schoolId)
      .then((s) => !cancelled && adopt(s))
      .catch(() => !cancelled && setLoadError("Couldn't load this school's payment settings."));
    return () => {
      cancelled = true;
    };
  }, [schoolId, adopt]);

  async function run(action: () => Promise<MpesaActionResult>) {
    setBusy(true);
    setNotice(null);
    try {
      const result = await action();
      adopt(result.status);
      setNotice({ ok: result.ok, text: result.message });
      return result;
    } catch (err) {
      setNotice({ ok: false, text: getErrorMessage(err, "That didn't work. Please try again.") });
    } finally {
      setBusy(false);
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const result = await run(() =>
      saveSchoolMpesa(schoolId, {
        environment,
        shortcode: shortcode.trim(),
        // Blank means "keep what is saved": never send an empty string over a real secret.
        ...(consumerKey.trim() ? { consumer_key: consumerKey.trim() } : {}),
        ...(consumerSecret.trim() ? { consumer_secret: consumerSecret.trim() } : {}),
        ...(passkey.trim() ? { passkey: passkey.trim() } : {}),
      }),
    );
    if (result) {
      setConsumerKey('');
      setConsumerSecret('');
      setPasskey('');
    }
  }

  if (loadError) return <p role="alert" className="mt-4 text-xs text-coral">{loadError}</p>;
  if (!status) return <p className="mt-4 text-xs text-ink-400">Loading payment settings…</p>;

  const tested = status.tested_at !== null;
  const saved = status.has_account;
  const secretPlaceholder = saved ? 'Saved. Leave blank to keep it' : '';

  return (
    <section aria-label={`M-Pesa for ${schoolName}`} className="mt-4 rounded-xl border border-white/[0.08] p-4 space-y-5">
      <div>
        <h3 className="font-display text-base text-ink-900">Online M-Pesa for {schoolName}</h3>
        <p className="mt-1 text-xs text-ink-400">
          Now: <strong className="text-ink-900">{MODE_LABEL[status.mode]}</strong>. {MODE_HELP[status.mode]}
        </p>
      </div>

      <form onSubmit={save} className="grid sm:grid-cols-2 gap-3" aria-label="School paybill details">
        <label className="text-xs text-ink-400">
          Environment
          <select value={environment} onChange={(e) => setEnvironment(e.target.value as MpesaEnvironment)} className={FIELD}>
            <option value="SANDBOX">Sandbox (test, no real money)</option>
            <option value="PRODUCTION">Live (real money)</option>
          </select>
        </label>
        <label className="text-xs text-ink-400">
          Paybill number
          <input required inputMode="numeric" pattern="\d{3,12}" value={shortcode} onChange={(e) => setShortcode(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400">
          Consumer key
          <input type="password" autoComplete="off" required={!saved} value={consumerKey} placeholder={secretPlaceholder} onChange={(e) => setConsumerKey(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400">
          Consumer secret
          <input type="password" autoComplete="off" required={!saved} value={consumerSecret} placeholder={secretPlaceholder} onChange={(e) => setConsumerSecret(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400 sm:col-span-2">
          Passkey
          <input type="password" autoComplete="off" required={!saved} value={passkey} placeholder={secretPlaceholder} onChange={(e) => setPasskey(e.target.value)} className={FIELD} />
        </label>
        <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
          <button disabled={busy} className="rounded-full bg-lime text-[#0B1203] font-semibold text-sm px-5 py-2 disabled:opacity-50">
            Save details
          </button>
          <span className="text-xs text-ink-400">Stored encrypted. They can be replaced but never viewed again.</span>
        </div>
      </form>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <button className={BTN} disabled={busy || !saved} onClick={() => void run(() => testSchoolMpesa(schoolId))}>Test connection</button>
          <span className="text-xs text-ink-400">Last successful test: {when(status.tested_at)}</span>
        </div>
        <p className="text-xs text-ink-400">
          This checks the consumer key and secret only. The paybill number and passkey are proven by a real payment, so try a small one
          before telling parents.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <button className={BTN} disabled={busy || !saved || !status.addresses_ready} onClick={() => void run(() => registerSchoolMpesaUrls(schoolId))}>
            Register paybill addresses with Safaricom
          </button>
          <span className="text-xs text-ink-400">Registered: {when(status.c2b_registered_at)}</span>
        </div>
        {saved && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              className={`${BTN} hover:!border-amber/60`}
              disabled={busy}
              onClick={() =>
                window.confirm(
                  `Change ${schoolName}'s private webhook address?\n\nThe old address stops working at once, so use this only if it may have leaked. Direct paybill payments will not reach Ledgr until you click "Register paybill addresses" again. Payment prompts sent from Ledgr keep working. No other school is affected.`,
                ) && void run(() => rotateSchoolMpesaAddress(schoolId))
              }
            >
              Rotate webhook address
            </button>
            <span className="text-xs text-ink-400">Only if the address may have leaked.</span>
          </div>
        )}
        {status.mode === 'GLOBAL' && status.other_schools_on_global > 0 && (
          <p className="text-xs text-amber">
            This school shares the server-wide paybill with {status.other_schools_on_global} other school(s). Their money lands in one account.
            A paybill of its own for each school is safer.
          </p>
        )}
        {!status.addresses_ready && (
          <p className="text-xs text-amber">The server does not know its own public address yet. Set MPESA_CALLBACK_URL on the server first.</p>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-xs text-ink-400">Where should this school&apos;s parents pay?</p>
        <div className="flex flex-wrap gap-2">
          <button className={BTN} disabled={busy || status.mode === 'OFF'} onClick={() => void run(() => setSchoolMpesaMode(schoolId, 'OFF'))}>
            Turn off
          </button>
          <button
            className={BTN}
            disabled={busy || status.mode === 'GLOBAL' || !status.global_configured}
            title={status.global_configured ? undefined : 'The server-wide M-Pesa settings are not complete'}
            onClick={() => {
              // Money from every school on the server-wide paybill lands in ONE account: make that a deliberate yes.
              const others = status.other_schools_on_global;
              if (others > 0 && !window.confirm(`${others} other school(s) already use the server-wide paybill. Money from all of them would land in the same account, and direct payments with the same admission number can't be told apart.\n\nGive ${schoolName} its own paybill instead unless you really want to share. Share anyway?`)) return;
              void run(() => setSchoolMpesaMode(schoolId, 'GLOBAL', others > 0));
            }}
          >
            Use the server-wide paybill
          </button>
          <button
            className={`${BTN} ${status.mode === 'OWN' ? '!border-lime/50 text-lime' : ''}`}
            disabled={busy || status.mode === 'OWN' || !saved || !tested}
            title={tested ? undefined : 'Save the details and test the connection first'}
            onClick={() => void run(() => setSchoolMpesaMode(schoolId, 'OWN'))}
          >
            Use this school&apos;s own paybill
          </button>
          {saved && (
            <button
              className={`${BTN} hover:!border-coral/60 text-coral`}
              disabled={busy}
              onClick={() => window.confirm(`Remove ${schoolName}'s saved M-Pesa details? Online M-Pesa will be switched off for this school.`) && void run(() => removeSchoolMpesa(schoolId))}
            >
              Remove saved details
            </button>
          )}
        </div>
      </div>

      {notice && (
        <p role={notice.ok ? 'status' : 'alert'} className={`text-xs ${notice.ok ? 'text-green' : 'text-coral'}`}>
          {notice.text}
        </p>
      )}
      {!notice && status.last_error && <p role="alert" className="text-xs text-coral">{status.last_error}</p>}
    </section>
  );
}
