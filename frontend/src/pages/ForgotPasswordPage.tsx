import { useState, type FormEvent } from 'react';
import { BookOpen, MailCheck } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { forgotPassword } from '../api/auth';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await forgotPassword(email);
    } finally {
      // Always show the same confirmation, whether or not the email is
      // registered — the backend response is deliberately generic too.
      setLoading(false);
      setSent(true);
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
          {sent ? (
            <>
              <div className="flex items-center gap-2 mb-1">
                <MailCheck className="w-5 h-5 text-ink-900" strokeWidth={1.75} />
                <h1 className="font-display text-xl text-ink-900">Check your email</h1>
              </div>
              <p className="text-sm text-ink-600">
                If an account exists for <span className="text-ink-900">{email}</span>, we've sent a link to reset
                your password. It expires in 30 minutes.
              </p>
            </>
          ) : (
            <>
              <h1 className="font-display text-xl text-ink-900 mb-1">Reset your password</h1>
              <p className="text-sm text-ink-600 mb-6">
                Enter your email and we'll send you a link to set a new password.
              </p>

              <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
                <TextField
                  label="Email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                <Button type="submit" disabled={loading} className="mt-2">
                  {loading ? 'Sending…' : 'Send reset link'}
                </Button>
              </form>
            </>
          )}
        </div>

        <p className="text-center text-sm text-ink-600 mt-6">
          <a href="/login" className="text-ink-900 font-medium underline underline-offset-2">
            Back to sign in
          </a>
        </p>
      </div>
    </div>
  );
}
