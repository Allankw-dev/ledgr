import { useState, useRef, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, ShieldCheck, Fingerprint, CheckCircle2 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { PasswordField } from '../components/ui/PasswordField';
import { OtpInput } from '../components/ui/OtpInput';
import { login, verifyTwoFactorLogin, googleAuth, registerParent } from '../api/auth';
import { getLoginOptions, verifyLogin } from '../api/webauthn';
import { isPlatformAuthenticatorAvailable, performAuthentication } from '../lib/webauthnBrowser';
import { useAuthStore } from '../store/authStore';
import { GoogleSignInButton } from '../components/GoogleSignInButton';

type Mode = 'login' | 'signup';

/**
 * A short filtered-noise "whoosh", synthesized in the browser — no audio
 * file to bundle or host. Skipped entirely under prefers-reduced-motion,
 * since a motion cue with no corresponding motion feels mismatched.
 */
function useSlideWhoosh() {
  const ctxRef = useRef<AudioContext | null>(null);

  return (direction: 'forward' | 'back') => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    ctxRef.current = ctxRef.current ?? new (window.AudioContext || (window as any).webkitAudioContext)();
    const ctx = ctxRef.current;
    const duration = 0.32;

    const bufferSize = ctx.sampleRate * duration;
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

    const noise = ctx.createBufferSource();
    noise.buffer = buffer;

    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.Q.value = 0.7;
    const startFreq = direction === 'forward' ? 500 : 1800;
    const endFreq = direction === 'forward' ? 1800 : 500;
    filter.frequency.setValueAtTime(startFreq, ctx.currentTime);
    filter.frequency.exponentialRampToValueAtTime(endFreq, ctx.currentTime + duration);

    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.05, ctx.currentTime + 0.04);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

    noise.connect(filter).connect(gain).connect(ctx.destination);
    noise.start();
    noise.stop(ctx.currentTime + duration);
  };
}

interface AuthPageProps {
  /** Which side the card opens on. Toggling inside the card is purely
   * visual (mirrors the mockup) — it does not change the URL, so a
   * mid-slide refresh always lands back on whichever route was requested. */
  initialMode: Mode;
}

export function AuthPage({ initialMode }: AuthPageProps) {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const playWhoosh = useSlideWhoosh();

  const [mode, setMode] = useState<Mode>(initialMode);
  const loginPanelRef = useRef<HTMLDivElement>(null);
  const signupPanelRef = useRef<HTMLDivElement>(null);
  const skipFocusRef = useRef(true); // true on mount, so page load never steals focus

  function toggle(next: Mode) {
    if (next === mode) return;
    // The mode change must never be at the mercy of the sound effect — a
    // browser blocking AudioContext (autoplay policy, or any other reason)
    // used to throw here and abort this function before setMode ran,
    // which is what caused the card to go fully blank on toggle.
    setMode(next);
    try {
      playWhoosh(next === 'signup' ? 'forward' : 'back');
    } catch {
      /* the slide must work even if the browser won't allow audio */
    }
  }

  // Move focus into the panel that just became active — but not on first
  // mount, and not for the tiny window mid-slide (matches the mockup's
  // 50ms delay so focus lands after the panel is actually reachable).
  useEffect(() => {
    if (skipFocusRef.current) {
      skipFocusRef.current = false;
      return;
    }
    const panel = mode === 'signup' ? signupPanelRef.current : loginPanelRef.current;
    const firstInput = panel?.querySelector('input');
    if (firstInput) {
      const t = setTimeout(() => firstInput.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [mode]);

  // ---- Login state -------------------------------------------------
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);
  const [fingerprintAvailable, setFingerprintAvailable] = useState(false);
  const [fingerprintBusy, setFingerprintBusy] = useState(false);
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [code, setCode] = useState('');
  type VerifyStage = 'entering' | 'verifying' | 'success';
  const [verifyStage, setVerifyStage] = useState<VerifyStage>('entering');
  const [verifiedUser, setVerifiedUser] = useState<Parameters<typeof setSession>[1] | null>(null);
  // Guards against verifyCode firing twice for the same code — e.g. the
  // OTP boxes auto-submit on completion AND the user also hits Enter or
  // clicks the button in the same instant. Reset on failure so a retry
  // can fire again; deliberately left set on success since the panel is
  // about to navigate away.
  const autoVerifyingRef = useRef(false);

  useEffect(() => {
    isPlatformAuthenticatorAvailable().then(setFingerprintAvailable);
  }, []);

  function completeLogin(token: string, user: Parameters<typeof setSession>[1]) {
    setSession(token, user);
    navigate(user.role === 'PARENT' ? '/parent/dashboard' : user.role === 'TEACHER' ? '/class-groups' : '/dashboard');
  }

  async function handleFingerprintSignIn() {
    setLoginError(null);
    setFingerprintBusy(true);
    try {
      const { options, challenge_id } = await getLoginOptions();
      const credential = await performAuthentication(options);
      const result = await verifyLogin(challenge_id, credential);
      completeLogin(result.token, result.user);
    } catch (err: unknown) {
      const name = (err as { name?: string })?.name;
      if (name !== 'NotAllowedError') {
        setLoginError("Couldn't sign in with fingerprint. Try your password instead.");
      }
    } finally {
      setFingerprintBusy(false);
    }
  }

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setLoginError(null);
    setLoginLoading(true);
    try {
      const result = await login(email, password);
      if ('requires_2fa' in result) {
        setChallengeToken(result.challenge_token);
      } else {
        completeLogin(result.token, result.user);
      }
    } catch {
      setLoginError('Incorrect email or password. Check your details and try again.');
    } finally {
      setLoginLoading(false);
    }
  }

  async function handleLoginGoogleCredential(credential: string) {
    setLoginError(null);
    setLoginLoading(true);
    try {
      const result = await googleAuth(credential);
      if ('requires_2fa' in result) {
        setChallengeToken(result.challenge_token);
      } else {
        completeLogin(result.token, result.user);
      }
    } catch {
      setLoginError('Could not sign in with Google. Please try again.');
    } finally {
      setLoginLoading(false);
    }
  }

  async function verifyCode(codeToVerify: string) {
    if (!challengeToken || autoVerifyingRef.current) return;
    if (codeToVerify.length !== 6) return;
    autoVerifyingRef.current = true;
    setLoginError(null);
    setVerifyStage('verifying');
    try {
      const result = await verifyTwoFactorLogin(challengeToken, codeToVerify);
      // Hold on a polished "welcome" moment before navigating, instead of
      // snapping straight to the dashboard — the success state is real
      // (session is usable from here on), navigation is just deliberately
      // delayed a beat so the confirmation is actually seen.
      setVerifiedUser(result.user);
      setVerifyStage('success');
      setTimeout(() => completeLogin(result.token, result.user), 1100);
    } catch {
      setLoginError('Incorrect code. Check your authenticator app and try again.');
      setVerifyStage('entering');
      setCode('');
      autoVerifyingRef.current = false;
    }
  }

  function handleCodeFormSubmit(e: FormEvent) {
    e.preventDefault();
    verifyCode(code);
  }

  // ---- Signup state --------------------------------------------------
  const [suFullName, setSuFullName] = useState('');
  const [suEmail, setSuEmail] = useState('');
  const [suPassword, setSuPassword] = useState('');
  const [suAdmissionNumber, setSuAdmissionNumber] = useState('');
  const [suError, setSuError] = useState<string | null>(null);
  const [suLoading, setSuLoading] = useState(false);

  function validateSignup(): string | null {
    if (suFullName.trim().length < 2) return 'Enter your full name.';
    if (suPassword.length < 8) return 'Password must be at least 8 characters.';
    if (suAdmissionNumber.trim().length < 1) return "Enter your child's admission number.";
    return null;
  }

  async function handleSignupSubmit(e: FormEvent) {
    e.preventDefault();
    const validationError = validateSignup();
    if (validationError) {
      setSuError(validationError);
      return;
    }
    setSuError(null);
    setSuLoading(true);
    try {
      const { token, user } = await registerParent({
        full_name: suFullName.trim(),
        email: suEmail.trim(),
        password: suPassword,
      });
      setSession(token, user);
      navigate('/verify-child', { state: { admissionNumber: suAdmissionNumber.trim() } });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setSuError(
        status === 409
          ? 'An account with this email already exists. Try signing in instead.'
          : 'Could not create your account. Check your details and try again.'
      );
    } finally {
      setSuLoading(false);
    }
  }

  async function handleSignupGoogleCredential(credential: string) {
    setSuError(null);
    setSuLoading(true);
    try {
      const result = await googleAuth(credential);
      if ('requires_2fa' in result) {
        // Parent accounts can't have 2FA enabled — only staff can. Seeing
        // this here means the email belongs to a staff account.
        setSuError('This email belongs to a staff account. Please sign in from the staff login instead.');
        return;
      }
      setSession(result.token, result.user);
      navigate('/verify-child');
    } catch {
      setSuError('Could not sign up with Google. Please try again.');
    } finally {
      setSuLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="glow-violet" />
      <div className="glow-cyan" />

      <div className="relative z-10 flex flex-col items-center">
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-[#06110B]" strokeWidth={2} />
          </div>
          <span className="font-display text-2xl text-ink-900 font-medium">Ledgr</span>
        </div>

        <div className="auth-card" data-mode={mode}>
          <div className="auth-forms-row">
            {/* ---------------- LOGIN PANEL ---------------- */}
            <div className="auth-form-panel auth-form-panel--login" data-hidden={mode !== 'login'} ref={loginPanelRef} inert={mode !== 'login'}>
              <div className="auth-form-inner">
              {!challengeToken ? (
                <>
                  {fingerprintAvailable && (
                    <>
                      <button
                        type="button"
                        onClick={handleFingerprintSignIn}
                        disabled={fingerprintBusy}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md border border-ink-200 text-sm font-medium text-ink-900 hover:bg-ink-100 transition-colors mb-4 disabled:opacity-50"
                      >
                        {fingerprintBusy ? <span className="orbit-spinner" /> : <Fingerprint className="w-4 h-4" strokeWidth={2} />}
                        {fingerprintBusy ? 'Waiting for fingerprint…' : 'Sign in with fingerprint'}
                      </button>
                      <div className="flex items-center gap-3 mb-4">
                        <div className="h-px bg-ink-200 flex-1" />
                        <span className="text-xs text-ink-400">or use your password</span>
                        <div className="h-px bg-ink-200 flex-1" />
                      </div>
                    </>
                  )}

                  <h1 className="font-display text-xl text-ink-900 mb-1">Sign in</h1>
                  <p className="text-sm text-ink-600 mb-6">Access your school's fee dashboard.</p>

                  <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-4" noValidate>
                    <TextField
                      label="Email"
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="neu-input"
                      required
                    />
                    <TextField
                      label="Password"
                      type="password"
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="neu-input"
                      required
                    />
                    <a href="/forgot-password" className="text-sm text-ink-600 hover:underline underline-offset-2 -mt-2 self-end">
                      Forgot password?
                    </a>

                    {loginError && (
                      <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
                        {loginError}
                      </p>
                    )}

                    <Button type="submit" disabled={loginLoading} className="mt-2 flex items-center justify-center gap-2">
                      {loginLoading && <span className="orbit-spinner" />}
                      {loginLoading ? 'Signing in…' : 'Sign in'}
                    </Button>
                  </form>

                  <div className="flex items-center gap-3 my-5">
                    <div className="h-px bg-ink-200 flex-1" />
                    <span className="text-xs text-ink-400">or</span>
                    <div className="h-px bg-ink-200 flex-1" />
                  </div>

                  <div className="flex justify-center">
                    <GoogleSignInButton onCredential={handleLoginGoogleCredential} text="signin_with" />
                  </div>

                  <p className="text-center text-sm text-ink-600 mt-6 md:hidden">
                    New here?{' '}
                    <button type="button" onClick={() => toggle('signup')} className="text-ink-900 font-medium underline underline-offset-2">
                      Create an account
                    </button>
                  </p>
                </>
              ) : verifyStage === 'success' ? (
                <div className="flex flex-col items-center justify-center text-center py-10 welcome-pop">
                  <div className="w-14 h-14 rounded-full bg-emerald-700/15 flex items-center justify-center mb-4">
                    <CheckCircle2 className="w-8 h-8 text-emerald-700" strokeWidth={2} />
                  </div>
                  <h1 className="font-display text-2xl text-ink-900 mb-1">
                    Welcome back{verifiedUser?.full_name ? `, ${verifiedUser.full_name.split(' ')[0]}` : ''}!
                  </h1>
                  <p className="text-sm text-ink-600">Taking you to your dashboard…</p>
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-2 mb-1">
                    <ShieldCheck className="w-5 h-5 text-ink-900" strokeWidth={1.75} />
                    <h1 className="font-display text-xl text-ink-900">Two-factor code</h1>
                  </div>
                  <p className="text-sm text-ink-600 mb-6">Enter the 6-digit code from your authenticator app.</p>

                  <form onSubmit={handleCodeFormSubmit} className="flex flex-col gap-5" noValidate>
                    <OtpInput
                      length={6}
                      value={code}
                      onChange={setCode}
                      onComplete={verifyCode}
                      spinning={verifyStage === 'verifying'}
                    />

                    {verifyStage === 'verifying' ? (
                      <p className="text-center text-sm text-ink-600 py-1">Verifying…</p>
                    ) : (
                      <>
                        {loginError && (
                          <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2 text-center">
                            {loginError}
                          </p>
                        )}
                        <Button type="submit" disabled={code.length !== 6} className="mt-1 flex items-center justify-center gap-2">
                          Verify and sign in
                        </Button>
                        <button
                          type="button"
                          onClick={() => {
                            setChallengeToken(null);
                            setCode('');
                            setLoginError(null);
                          }}
                          className="text-sm text-ink-600 hover:underline underline-offset-2 text-center"
                        >
                          Back to sign in
                        </button>
                      </>
                    )}
                  </form>
                </>
              )}
              </div>
            </div>

            {/* ---------------- SIGNUP PANEL ---------------- */}
            <div className="auth-form-panel auth-form-panel--signup" data-hidden={mode !== 'signup'} ref={signupPanelRef} inert={mode !== 'signup'}>
              <div className="auth-form-inner">
              <h1 className="font-display text-xl text-ink-900 mb-1">Parent sign up</h1>
              <p className="text-sm text-ink-600 mb-6">Create your account, then we'll verify your child's details.</p>

              <div className="flex justify-center mb-5">
                <GoogleSignInButton onCredential={handleSignupGoogleCredential} text="signup_with" />
              </div>

              <div className="flex items-center gap-3 mb-5">
                <div className="h-px bg-ink-200 flex-1" />
                <span className="text-xs text-ink-400">or</span>
                <div className="h-px bg-ink-200 flex-1" />
              </div>

              <form onSubmit={handleSignupSubmit} className="flex flex-col gap-4" noValidate>
                <TextField
                  label="Your full name"
                  value={suFullName}
                  onChange={(e) => setSuFullName(e.target.value)}
                  placeholder="e.g. Jane Wambui"
                  className="neu-input"
                  required
                />
                <TextField
                  label="Email"
                  type="email"
                  autoComplete="email"
                  value={suEmail}
                  onChange={(e) => setSuEmail(e.target.value)}
                  className="neu-input"
                  required
                />
                <PasswordField
                  label="Password"
                  autoComplete="new-password"
                  value={suPassword}
                  onChange={(e) => setSuPassword(e.target.value)}
                  className="neu-input"
                  required
                />
                <hr className="border-ink-100 my-1" />
                <TextField
                  label="Child's admission number"
                  value={suAdmissionNumber}
                  onChange={(e) => setSuAdmissionNumber(e.target.value)}
                  placeholder="e.g. GA-2026-014"
                  className="neu-input"
                  required
                />

                {suError && (
                  <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
                    {suError}
                  </p>
                )}

                <Button type="submit" disabled={suLoading} className="mt-2 flex items-center justify-center gap-2">
                  {suLoading && <span className="orbit-spinner" />}
                  {suLoading ? 'Creating account…' : 'Continue'}
                </Button>
              </form>

              <p className="text-center text-sm text-ink-600 mt-6 md:hidden">
                Already have an account?{' '}
                <button type="button" onClick={() => toggle('login')} className="text-ink-900 font-medium underline underline-offset-2">
                  Sign in
                </button>
              </p>
              </div>
            </div>
          </div>

          {/* ---------------- SLIDING ACCENT OVERLAY (desktop only) ---------------- */}
          <div className="auth-overlay-track">
            <div className="auth-overlay">
              <div className="auth-overlay-panel auth-overlay-panel--signup-cta">
                <h2 className="font-display text-2xl text-white mb-3">New to Ledgr?</h2>
                <p className="text-sm text-white/85 leading-relaxed mb-6">
                  Create a parent account to track fees, pay via M-Pesa, and stay in touch with the school.
                </p>
                <button type="button" onClick={() => toggle('signup')} className="auth-overlay-btn">
                  Create account
                </button>
              </div>
              <div className="auth-overlay-panel auth-overlay-panel--login-cta">
                <h2 className="font-display text-2xl text-white mb-3">Already a member?</h2>
                <p className="text-sm text-white/85 leading-relaxed mb-6">
                  Sign in to see your children's balances and recent payments.
                </p>
                <button type="button" onClick={() => toggle('login')} className="auth-overlay-btn">
                  Sign in
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
