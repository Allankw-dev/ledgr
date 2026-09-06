import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { PasswordField } from '../components/ui/PasswordField';
import { registerParent, googleAuth } from '../api/auth';
import { useAuthStore } from '../store/authStore';
import { GoogleSignInButton } from '../components/GoogleSignInButton';

export function ParentSignUpPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [admissionNumber, setAdmissionNumber] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function validate(): string | null {
    if (fullName.trim().length < 2) return 'Enter your full name.';
    if (password.length < 8) return 'Password must be at least 8 characters.';
    if (admissionNumber.trim().length < 1) return "Enter your child's admission number.";
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const { token, user } = await registerParent({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });
      setSession(token, user);
      navigate('/verify-child', { state: { admissionNumber: admissionNumber.trim() } });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(
        status === 409
          ? 'An account with this email already exists. Try signing in instead.'
          : 'Could not create your account. Check your details and try again.'
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleCredential(credential: string) {
    setError(null);
    setLoading(true);
    try {
      const result = await googleAuth(credential);
      if ('requires_2fa' in result) {
        // Parent accounts can't have 2FA enabled — only SCHOOL_ADMIN/BURSAR
        // can. Seeing this here means the email belongs to a staff account.
        setError('This email belongs to a staff account. Please sign in from the staff login instead.');
        return;
      }
      setSession(result.token, result.user);
      navigate('/verify-child');
    } catch {
      setError('Could not sign up with Google. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="w-9 h-9 rounded-md bg-ink-900 flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-paper" strokeWidth={2} />
          </div>
          <span className="font-display text-2xl text-ink-900 font-medium">Ledgr</span>
        </div>

        <div className="bg-white border border-ink-200 rounded-lg p-8 shadow-sm">
          <h1 className="font-display text-xl text-ink-900 mb-1">Parent sign up</h1>
          <p className="text-sm text-ink-600 mb-6">
            Create your account, then we'll verify your child's details.
          </p>

          <div className="flex justify-center mb-5">
            <GoogleSignInButton onCredential={handleGoogleCredential} text="signup_with" />
          </div>

          <div className="flex items-center gap-3 mb-5">
            <div className="h-px bg-ink-200 flex-1" />
            <span className="text-xs text-ink-400">or</span>
            <div className="h-px bg-ink-200 flex-1" />
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <TextField
              label="Your full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Jane Wambui"
              required
            />
            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <PasswordField
              label="Password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <hr className="border-ink-100 my-1" />
            <TextField
              label="Child's admission number"
              value={admissionNumber}
              onChange={(e) => setAdmissionNumber(e.target.value)}
              placeholder="e.g. GA-2026-014"
              required
            />

            {error && (
              <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <Button type="submit" disabled={loading} className="mt-2">
              {loading ? 'Creating account…' : 'Continue'}
            </Button>
          </form>
        </div>

        <p className="text-center text-sm text-ink-600 mt-6">
          Already have an account?{' '}
          <a href="/login" className="text-ink-900 font-medium underline underline-offset-2">
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
}
