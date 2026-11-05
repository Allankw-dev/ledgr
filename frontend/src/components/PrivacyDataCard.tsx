import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { deleteMyAccount, getPrivacySettings, setEmailOptOut } from '../api/privacy';
import { useAuthStore } from '../store/authStore';
import { getErrorMessage } from '../api/client';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';
import { TextField } from './ui/TextField';

/** Parent profile: control optional email, see what was agreed, and erase the account. */
export function PrivacyDataCard() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const [optOut, setOptOut] = useState<boolean | null>(null);
  const [acceptedAt, setAcceptedAt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);

  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState('');
  const [typed, setTyped] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    getPrivacySettings()
      .then((s) => {
        setOptOut(s.email_opt_out);
        setAcceptedAt(s.terms_accepted_at);
      })
      .catch(() => setEmailError('Could not load your privacy settings.'));
  }, []);

  async function toggleEmail(next: boolean) {
    setSaving(true);
    setEmailError(null);
    try {
      const res = await setEmailOptOut(next);
      setOptOut(res.email_opt_out);
    } catch (err) {
      setEmailError(getErrorMessage(err, 'Could not save that. Please try again.'));
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteMyAccount(password, typed);
      logout();
      navigate('/login', { replace: true });
    } catch (err) {
      setDeleteError(getErrorMessage(err, 'Could not delete your account. Please try again.'));
      setDeleting(false);
    }
  }

  function closeDelete() {
    setConfirming(false);
    setPassword('');
    setTyped('');
    setDeleteError(null);
  }

  return (
    <section aria-labelledby="privacy-data-heading" className="bg-panel border border-ink-200 rounded-lg px-5 py-4">
      <h2 id="privacy-data-heading" className="text-sm text-ink-900 font-medium mb-3">Privacy &amp; data</h2>

      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <p className="text-sm text-ink-900" id="email-pref-label">Reminders and announcements by email</p>
          <p className="text-xs text-ink-600 mt-0.5" id="email-pref-help">
            Payment receipts and security emails are always sent.
          </p>
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-ink-700 shrink-0">
          <input
            type="checkbox"
            className="h-4 w-4 accent-[#39FF88]"
            checked={optOut === false}
            disabled={optOut === null || saving}
            onChange={(e) => void toggleEmail(!e.target.checked)}
            aria-labelledby="email-pref-label"
            aria-describedby="email-pref-help"
          />
          {optOut === false ? 'On' : 'Off'}
        </label>
      </div>
      {emailError && <p role="alert" className="text-xs text-clay-700 mb-3">{emailError}</p>}

      {acceptedAt && (
        <p className="text-xs text-ink-600 mb-4">
          You accepted the <Link to="/terms" className="underline">Terms</Link> and <Link to="/privacy" className="underline">Privacy Policy</Link> on{' '}
          {new Date(acceptedAt).toLocaleDateString('en-KE', { day: 'numeric', month: 'long', year: 'numeric' })}.
        </p>
      )}

      <div className="border-t border-ink-200 pt-4">
        <p className="text-sm text-ink-900 mb-1">Delete my account</p>
        <p className="text-xs text-ink-600 mb-3">
          Removes your name, email, phone, password, links to your children, messages and chat posts, and signs you out everywhere.
          Payments stay on the school&apos;s books but no longer show your details. This cannot be undone.
        </p>
        <Button type="button" variant="secondary" onClick={() => setConfirming(true)}>Delete my account…</Button>
      </div>

      {confirming && (
        <Modal title="Delete your account?" onClose={closeDelete}>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              void confirmDelete();
            }}
          >
            <p className="text-sm text-ink-700">
              This permanently removes your personal details from Ledgr. To ask the school to change or erase your child&apos;s record, contact the school office instead.
            </p>
            <TextField
              label="Your password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <TextField
              label="Type DELETE to confirm"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              required
            />
            <p className="text-xs text-ink-600">Signed up with Google and never set a password? Use “Forgot password” on the sign-in page to set one first.</p>
            {deleteError && <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">{deleteError}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={closeDelete}>Cancel</Button>
              <Button type="submit" disabled={deleting || !password || typed.trim().toUpperCase() !== 'DELETE'}>
                {deleting ? 'Deleting…' : 'Delete my account'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
