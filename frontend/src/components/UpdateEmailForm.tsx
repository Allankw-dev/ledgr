import { useState } from 'react';
import { Mail, Check } from 'lucide-react';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { requestEmailChange } from '../api/auth';
import { getErrorMessage } from '../api/client';

const PLACEHOLDER_DOMAIN = '@phone.ledgr.invalid';

interface UpdateEmailFormProps {
  currentEmail: string;
}

// Changing the sign-in email takes two proofs: the current password (so an
// unlocked, already-signed-in phone can't be used to redirect the account) and
// a link that only works from the NEW inbox. The change itself is applied on
// the confirm page (ConfirmEmailPage) — nothing changes until that link is opened.
export function UpdateEmailForm({ currentEmail }: UpdateEmailFormProps) {
  const hasRealEmail = !currentEmail.toLowerCase().endsWith(PLACEHOLDER_DOMAIN);
  const [editing, setEditing] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await requestEmailChange(newEmail.trim(), password);
      setSentTo(newEmail.trim());
      setEditing(false);
      setPassword('');
      setNewEmail('');
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not start the email change. Try again.'));
    } finally {
      setSubmitting(false);
    }
  }

  if (!editing) {
    return (
      <div>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 text-sm min-w-0">
            <Mail className="w-4 h-4 text-ink-400 shrink-0" strokeWidth={1.75} />
            <span className="text-ink-900 truncate">
              {hasRealEmail ? currentEmail : 'No email on file — you sign in with your phone number'}
            </span>
          </div>
          <button
            onClick={() => {
              setSentTo(null);
              setEditing(true);
            }}
            className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 shrink-0"
          >
            {hasRealEmail ? 'Change email' : 'Add email'}
          </button>
        </div>
        {sentTo && (
          <p className="mt-3 flex items-start gap-1.5 text-xs text-emerald-700" role="status">
            <Check className="w-3.5 h-3.5 mt-px shrink-0" />
            <span>
              We sent a confirmation link to <span className="font-medium">{sentTo}</span>. Open it to finish — your
              email stays as it is until you do. You'll then sign in again with the new address.
            </span>
          </p>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <p className="text-xs text-ink-600">
        Lost access to your old email? Enter the new one and your password. We'll send a link to the new address to
        confirm it's yours.
      </p>
      <TextField
        label="New email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        value={newEmail}
        onChange={(e) => setNewEmail(e.target.value)}
        required
        autoFocus
      />
      <TextField
        label="Your current password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <p className="text-xs text-ink-400">
        Signed up with Google and never set a password? Use "Forgot password" on the sign-in page to set one first.
      </p>
      {error && <p className="text-sm text-clay-700">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={() => setEditing(false)} className="text-xs px-3 py-1.5">
          Cancel
        </Button>
        <Button type="submit" disabled={submitting || !newEmail || !password} className="text-xs px-3 py-1.5">
          {submitting ? 'Sending…' : 'Send confirmation link'}
        </Button>
      </div>
    </form>
  );
}
