import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, ShieldCheck } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { login, verifyTwoFactorLogin } from '../api/auth';
import { useAuthStore } from '../store/authStore';

export function LoginPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Set once the server confirms the password was correct but 2FA is required —
  // switches the form into "enter your authenticator code" mode.
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [code, setCode] = useState('');

  function completeLogin(token: string, user: Parameters<typeof setSession>[1]) {
    setSession(token, user);
    navigate(user.role === 'PARENT' ? '/parent/dashboard' : '/dashboard');
  }

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login(email, password);
      if ('requires_2fa' in result) {
        setChallengeToken(result.challenge_token);
      } else {
        completeLogin(result.token, result.user);
      }
    } catch {
      setError('Incorrect email or password. Check your details and try again.');
    } finally {
      setLoading(false);
    }
  }

  async function handleCodeSubmit(e: FormEvent) {
    e.preventDefault();
    if (!challengeToken) return;
    setError(null);
    setLoading(true);
    try {
      const result = await verifyTwoFactorLogin(challengeToken, code);
      completeLogin(result.token, result.user);
    } catch {
      setError('Incorrect code. Check your authenticator app and try again.');
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
          {!challengeToken ? (
            <>
              <h1 className="font-display text-xl text-ink-900 mb-1">Sign in</h1>
              <p className="text-sm text-ink-600 mb-6">Access your school's fee dashboard.</p>

              <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-4" noValidate>
                <TextField
                  label="Email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                <TextField
                  label="Password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />

                {error && (
                  <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
                    {error}
                  </p>
                )}

                <Button type="submit" disabled={loading} className="mt-2">
                  {loading ? 'Signing in…' : 'Sign in'}
                </Button>
              </form>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1">
                <ShieldCheck className="w-5 h-5 text-ink-900" strokeWidth={1.75} />
                <h1 className="font-display text-xl text-ink-900">Two-factor code</h1>
              </div>
              <p className="text-sm text-ink-600 mb-6">Enter the 6-digit code from your authenticator app.</p>

              <form onSubmit={handleCodeSubmit} className="flex flex-col gap-4" noValidate>
                <TextField
                  label="Authentication code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  placeholder="000000"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  autoFocus
                  required
                />

                {error && (
                  <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
                    {error}
                  </p>
                )}

                <Button type="submit" disabled={loading || code.length !== 6} className="mt-2">
                  {loading ? 'Verifying…' : 'Verify and sign in'}
                </Button>
                <button
                  type="button"
                  onClick={() => {
                    setChallengeToken(null);
                    setCode('');
                    setError(null);
                  }}
                  className="text-sm text-ink-600 hover:underline underline-offset-2"
                >
                  Back to sign in
                </button>
              </form>
            </>
          )}
        </div>

        <p className="text-center text-sm text-ink-600 mt-6">
          New parent?{' '}
          <a href="/signup" className="text-ink-900 font-medium underline underline-offset-2">
            Sign up
          </a>
        </p>
      </div>
    </div>
  );
}
