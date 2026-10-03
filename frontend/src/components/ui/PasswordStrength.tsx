/** Four-segment strength meter shown under a new-password field. Advice only — it never blocks sign-up. */
export function PasswordStrength({ value }: { value: string }) {
  if (!value) return null;

  let score = 0;
  if (value.length >= 8) score++;
  if (value.length >= 12) score++;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score++;
  if (/\d/.test(value) && /[^A-Za-z0-9]/.test(value)) score++;
  if (value.length < 8) score = Math.min(score, 1);

  const levels = [
    { label: 'Too short', bar: 'bg-clay-600', text: 'text-clay-700' },
    { label: 'Weak', bar: 'bg-clay-600', text: 'text-clay-700' },
    { label: 'Fair', bar: 'bg-amber', text: 'text-amber' },
    { label: 'Good', bar: 'bg-green', text: 'text-green' },
    { label: 'Strong', bar: 'bg-green', text: 'text-green' },
  ];
  const level = levels[score];

  return (
    <div className="-mt-2 flex items-center gap-2" aria-live="polite">
      <div className="flex flex-1 gap-1">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={`h-1 flex-1 rounded-full transition-colors duration-300 ${i <= score ? level.bar : 'bg-white/10'}`} />
        ))}
      </div>
      <span className={`text-xs font-medium ${level.text}`}>{level.label}</span>
    </div>
  );
}
