import { friendlyName } from '../lib/names';
import { useState, useRef, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, ShieldCheck, Fingerprint, CheckCircle2, Mail, Lock, UserRound, Phone, GraduationCap, ArrowRight, AlertCircle, Smartphone, Wallet, MessageCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { PasswordField } from '../components/ui/PasswordField';
import { PasswordStrength } from '../components/ui/PasswordStrength';
import { OtpInput } from '../components/ui/OtpInput';
import { login, verifyTwoFactorLogin, googleAuth, registerParent } from '../api/auth';
import { getErrorMessage } from '../api/client';
import { getLoginOptions, verifyLogin } from '../api/webauthn';
import { isPlatformAuthenticatorAvailable, performAuthentication } from '../lib/webauthnBrowser';
import { useAuthStore } from '../store/authStore';
import { GoogleSignInButton } from '../components/GoogleSignInButton';
import { AuthArches, OverlayArches } from '../components/AuthArches';
import { useFitToViewport } from '../hooks/useFitToViewport';

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

/** Phone-only switch between the two screens (the sliding side panel does this on desktop). */
function AuthSwitch({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  const tabs: { id: Mode; label: string }[] = [
    { id: 'login', label: 'Sign in' },
    { id: 'signup', label: 'Create account' },
  ];
  return (
    <div className="md:hidden relative grid grid-cols-2 p-1 mb-6 rounded-full bg-black/25 ring-1 ring-white/10" role="tablist">
      <span
        aria-hidden="true"
        className="bottom-nav-pill absolute top-1 bottom-1 left-1 w-[calc(50%-4px)] rounded-full bg-emerald-100 ring-1 ring-green/25 shadow-[0_0_18px_-4px_rgba(57,255,136,0.5)]"
        style={{ transform: `translateX(${mode === 'signup' ? 100 : 0}%)` }}
      />
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={mode === t.id}
          onClick={() => onChange(t.id)}
          className={`relative z-10 py-2 text-sm font-medium transition-colors ${mode === t.id ? 'text-green' : 'text-ink-600'}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function AuthHeading({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle: string }) {
  return (
    <div className="mb-5">
      <span className="inline-flex items-center gap-1.5 rounded-full bg-green/10 ring-1 ring-green/20 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-green mb-3">
        <span className="w-1.5 h-1.5 rounded-full bg-green animate-pulse" aria-hidden="true" />
        {eyebrow}
      </span>
      <h1 className="auth-title font-display text-[1.65rem] leading-tight text-ink-900">{title}</h1>
      <p className="text-sm text-ink-600 mt-1.5">{subtitle}</p>
    </div>
  );
}

function AuthAlert({ children, center = false }: { children: React.ReactNode; center?: boolean }) {
  return (
    <p role="alert" className={`pop-in flex items-start gap-2 text-sm text-clay-700 bg-clay-100 rounded-lg px-3 py-2.5 ${center ? 'justify-center text-center' : ''}`}>
      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={2} />
      <span>{children}</span>
    </p>
  );
}

function TrustNote() {
  return (
    <p className="mt-5 flex items-center justify-center gap-1.5 text-xs text-ink-400">
      <Lock className="w-3 h-3" strokeWidth={2} />
      Encrypted connection · your details stay private
    </p>
  );
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

  function completeLogin(token: string, user: Parameters<typeof setSession>[1], refreshToken?: string | null) {
    setSession(token, user, refreshToken);
    navigate(user.role === 'PARENT' ? '/parent/dashboard' : user.role === 'TEACHER' ? '/class-groups' : '/dashboard');
  }

  async function handleFingerprintSignIn() {
    setLoginError(null);
    setFingerprintBusy(true);
    try {
      const { options, challenge_id } = await getLoginOptions();
      const credential = await performAuthentication(options);
      const result = await verifyLogin(challenge_id, credential);
      completeLogin(result.token, result.user, result.refresh_token);
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
        completeLogin(result.token, result.user, result.refresh_token);
      }
    } catch {
      setLoginError('Incorrect email/phone or password. Check your details and try again.');
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
        completeLogin(result.token, result.user, result.refresh_token);
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
      setTimeout(() => completeLogin(result.token, result.user, result.refresh_token), 1100);
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
  const [suPhone, setSuPhone] = useState('');
  const [suPassword, setSuPassword] = useState('');
  const [suAdmissionNumber, setSuAdmissionNumber] = useState('');
  const [suError, setSuError] = useState<string | null>(null);
  const [suLoading, setSuLoading] = useState(false);

  function validateSignup(): string | null {
    if (suFullName.trim().length < 2) return 'Enter your full name.';
    if (suPhone.trim().length < 7) return 'Enter a valid phone number.';
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
      const { token, user, refresh_token } = await registerParent({
        full_name: suFullName.trim(),
        email: suEmail.trim(),
        phone: suPhone.trim(),
        password: suPassword,
      });
      setSession(token, user, refresh_token);
      navigate('/verify-child', { state: { admissionNumber: suAdmissionNumber.trim() } });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setSuError(
        status === 409
          ? getErrorMessage(err, 'An account with this email already exists. Try signing in instead.')
          : getErrorMessage(err, 'Could not create your account. Check your details and try again.')
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
      setSession(result.token, result.user, result.refresh_token);
      navigate('/verify-child');
    } catch {
      setSuError('Could not sign up with Google. Please try again.');
    } finally {
      setSuLoading(false);
    }
  }

  // Keep the whole card (logo + forms) inside the window — no scrolling up and down.
  const fitRef = useRef<HTMLDivElement>(null);
  useFitToViewport(fitRef);

  return (
    <div className="auth-shell">
      <AuthArches />

      <div ref={fitRef} className="auth-fit relative z-10 flex flex-col items-center">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shadow-[0_8px_24px_-6px_rgba(57,255,136,0.6)]">
            <BookOpen className="w-5 h-5 text-[#06110B]" strokeWidth={2.25} />
          </div>
          <span className="font-display text-2xl text-ink-900 font-semibold tracking-tight">Ledgr</span>
        </div>

        <div className="auth-card" data-mode={mode}>
          <div className="auth-forms-row">
            {/* ---------------- LOGIN PANEL ---------------- */}
            <div className="auth-form-panel auth-form-panel--login" data-hidden={mode !== 'login'} ref={loginPanelRef} inert={mode !== 'login'}>
              <div className="auth-form-inner">
              {!challengeToken ? (
                <>
                  <AuthSwitch mode={mode} onChange={toggle} />
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

                  <AuthHeading eyebrow="Sign in" title="Welcome back" subtitle="Access your school's fee dashboard." />

                  <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-4" noValidate>
                    <TextField
                      label="Email or phone number"
                      type="text"
                      autoComplete="username"
                      placeholder="you@example.com or 0712 345 678"
                      icon={<Mail />}
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="neu-input"
                      required
                    />
                    <PasswordField
                      label="Password"
                      autoComplete="current-password"
                      icon={<Lock />}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="neu-input"
                      required
                    />
                    <a href="/forgot-password" className="text-sm text-ink-600 hover:underline underline-offset-2 -mt-2 self-end">
                      Forgot password?
                    </a>

                    {loginError && <AuthAlert>{loginError}</AuthAlert>}

                    <Button type="submit" disabled={loginLoading} className="group mt-2 flex items-center justify-center gap-2">
                      {loginLoading && <span className="orbit-spinner" />}
                      {loginLoading ? (
                        'Signing in…'
                      ) : (
                        <>
                          Sign in
                          <ArrowRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-1" strokeWidth={2.25} />
                        </>
                      )}
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

                  <TrustNote />
                </>
              ) : verifyStage === 'success' ? (
                <div className="flex flex-col items-center justify-center text-center py-10 welcome-pop">
                  <div className="w-14 h-14 rounded-full bg-emerald-700/15 flex items-center justify-center mb-4">
                    <CheckCircle2 className="w-8 h-8 text-emerald-700" strokeWidth={2} />
                  </div>
                  <h1 className="font-display text-2xl text-ink-900 mb-1">
                    Welcome back{verifiedUser?.full_name ? `, ${friendlyName(verifiedUser.full_name)}` : ''}!
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
                        {loginError && <AuthAlert center>{loginError}</AuthAlert>}
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
              <AuthSwitch mode={mode} onChange={toggle} />
              <AuthHeading eyebrow="Parent sign up" title="Create your account" subtitle="Then we'll verify your child's details with the school." />

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
                  icon={<UserRound />}
                  className="neu-input"
                  required
                />
                <TextField
                  label="Email"
                  type="email"
                  autoComplete="email"
                  icon={<Mail />}
                  value={suEmail}
                  onChange={(e) => setSuEmail(e.target.value)}
                  className="neu-input"
                  required
                />
                <TextField
                  label="Phone number"
                  type="tel"
                  autoComplete="tel"
                  placeholder="e.g. +254712345678"
                  icon={<Phone />}
                  value={suPhone}
                  onChange={(e) => setSuPhone(e.target.value)}
                  className="neu-input"
                  required
                />
                <PasswordField
                  label="Password"
                  autoComplete="new-password"
                  icon={<Lock />}
                  value={suPassword}
                  onChange={(e) => setSuPassword(e.target.value)}
                  className="neu-input"
                  required
                />
                <PasswordStrength value={suPassword} />
                <hr className="border-white/10 my-1" />
                <TextField
                  label="Child's admission number"
                  value={suAdmissionNumber}
                  onChange={(e) => setSuAdmissionNumber(e.target.value)}
                  placeholder="e.g. GA-2026-014"
                  icon={<GraduationCap />}
                  className="neu-input"
                  required
                />

                {suError && <AuthAlert>{suError}</AuthAlert>}

                <Button type="submit" disabled={suLoading} className="group mt-2 flex items-center justify-center gap-2">
                  {suLoading && <span className="orbit-spinner" />}
                  {suLoading ? (
                    'Creating account…'
                  ) : (
                    <>
                      Continue
                      <ArrowRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-1" strokeWidth={2.25} />
                    </>
                  )}
                </Button>
              </form>
              <TrustNote />
              </div>
            </div>
          </div>

          {/* ---------------- SLIDING ACCENT OVERLAY (desktop only) ---------------- */}
          <div className="auth-overlay-track">
            <div className="auth-overlay">
              <div className="auth-overlay-arc auth-overlay-arc--tr" />
              <div className="auth-overlay-arc auth-overlay-arc--bl" />
              <OverlayArches />
              <div className="auth-overlay-panel auth-overlay-panel--signup-cta">
                <h2 className="font-display text-2xl text-white mb-3">New to Ledgr?</h2>
                <p className="text-sm text-white/85 leading-relaxed mb-5">
                  Create a parent account and everything about your child's fees is in one place.
                </p>
                <ul className="flex flex-col gap-2.5 mb-6 text-left">
                  {[
                    { icon: Smartphone, text: 'Pay fees with M-Pesa' },
                    { icon: Wallet, text: 'Live balances and receipts' },
                    { icon: MessageCircle, text: 'Chat with teachers and the office' },
                  ].map(({ icon: Icon, text }) => (
                    <li key={text} className="flex items-center gap-2.5 text-[13px] text-white/90">
                      <span className="w-7 h-7 rounded-lg bg-white/15 ring-1 ring-white/20 flex items-center justify-center shrink-0">
                        <Icon className="w-4 h-4" strokeWidth={1.75} />
                      </span>
                      {text}
                    </li>
                  ))}
                </ul>
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
