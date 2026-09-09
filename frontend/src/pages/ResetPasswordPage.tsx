import { useState, type FormEvent } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { BookOpen, CheckCircle2 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { resetPassword } from '../api/auth';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    setLoading(true);
    try {
      await resetPassword(token, newPassword);
      setDone(true);
    } catch {
      setError('This reset link is invalid or has expired. Request a new one and try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="w-9 h-9 rounded-md bg-ink-900 flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-paper" strokeWidth={2} />
          </div>
          <span className="font-display text-2xl text-ink-900 font-medium">Ledgr</span>
        </div>

        <div className="bg-white border border-ink-200 rounded-lg p-8 shadow-sm">
          {!token ? (
            <p className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
              This link is missing its reset token. Request a new one from the sign-in page.
            </p>
          ) : done ? (
            <>
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="w-5 h-5 text-emerald-700" strokeWidth={1.75} />
                <h1 className="font-display text-xl text-ink-900">Password updated</h1>
              </div>
              <p className="text-sm text-ink-600 mb-6">You can now sign in with your new password.</p>
              <Button onClick={() => navigate('/login')}>Back to sign in</Button>
            </>
          ) : (
            <>
              <h1 className="font-display text-xl text-ink-900 mb-1">Set a new password</h1>
              <p className="text-sm text-ink-600 mb-6">Choose a new password for your account.</p>

              <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
                <TextField
                  label="New password"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                />
                <TextField
                  label="Confirm new password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />

                {error && (
                  <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
                    {error}
                  </p>
                )}

                <Button type="submit" disabled={loading} className="mt-2">
                  {loading ? 'Updating…' : 'Update password'}
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
