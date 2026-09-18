import { useRef, useEffect, type ClipboardEvent, type KeyboardEvent, type CSSProperties } from 'react';

interface OtpInputProps {
  length?: number;
  value: string;
  onChange: (value: string) => void;
  onComplete?: (value: string) => void;
  autoFocus?: boolean;
  /** Lights every box green once the code reaches full length — the same
     "verified" moment the reference design uses, just in Ledgr's own
     accent color rather than copying the reference's teal. */
  celebrateOnComplete?: boolean;
  /** True for exactly as long as the code is actually being checked
     against the server — not a fixed decorative duration. Each box
     spins continuously while this is true and settles the moment it
     goes false, so the motion's length always matches how long
     verification actually took, whether that's 200ms or 2 seconds. */
  spinning?: boolean;
}

// A small fixed set of directions boxes fan out toward while spinning —
// see the note in index.css on why this isn't computed via CSS trig.
const ORBIT_DIRECTIONS = [
  { x: '16px', y: '-16px' },
  { x: '-16px', y: '-16px' },
  { x: '16px', y: '16px' },
  { x: '-16px', y: '16px' },
  { x: '18px', y: '0px' },
  { x: '-18px', y: '0px' },
];

export function OtpInput({
  length = 6,
  value,
  onChange,
  onComplete,
  autoFocus = true,
  celebrateOnComplete = true,
  spinning = false,
}: OtpInputProps) {
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = value.padEnd(length, ' ').split('').slice(0, length);
  const isComplete = value.length === length;

  useEffect(() => {
    if (isComplete && onComplete) onComplete(value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isComplete]);

  function setDigit(index: number, char: string) {
    const next = digits.slice();
    next[index] = char;
    const joined = next.join('').trimEnd();
    onChange(joined);
  }

  function handleChange(index: number, raw: string) {
    const char = raw.replace(/\D/g, '').slice(-1);
    if (!char) {
      setDigit(index, ' ');
      return;
    }
    setDigit(index, char);
    if (index < length - 1) inputRefs.current[index + 1]?.focus();
  }

  function handleKeyDown(index: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace') {
      if (digits[index].trim()) {
        setDigit(index, ' ');
      } else if (index > 0) {
        inputRefs.current[index - 1]?.focus();
        setDigit(index - 1, ' ');
      }
      e.preventDefault();
    } else if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === 'ArrowRight' && index < length - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  }

  function handlePaste(e: ClipboardEvent<HTMLInputElement>) {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length);
    if (!pasted) return;
    onChange(pasted);
    const focusIndex = Math.min(pasted.length, length - 1);
    inputRefs.current[focusIndex]?.focus();
  }

  return (
    <div className="flex items-center justify-center gap-2.5" onPaste={handlePaste}>
      {digits.map((digit, i) => {
        const direction = ORBIT_DIRECTIONS[i % ORBIT_DIRECTIONS.length];
        return (
          <input
            key={i}
            ref={(el) => {
              inputRefs.current[i] = el;
            }}
            type="text"
            inputMode="numeric"
            autoComplete={i === 0 ? 'one-time-code' : 'off'}
            maxLength={1}
            value={digit.trim()}
            onChange={(e) => handleChange(i, e.target.value)}
            onKeyDown={(e) => handleKeyDown(i, e)}
            readOnly={spinning}
            autoFocus={autoFocus && i === 0}
            aria-label={`Digit ${i + 1} of ${length}`}
            style={{ '--orbit-x': direction.x, '--orbit-y': direction.y, animationDelay: `${i * 40}ms` } as CSSProperties}
            className={`w-11 h-[52px] sm:w-12 sm:h-14 rounded-xl border text-center text-lg font-semibold bg-ink-100 text-ink-900 transition-all duration-200 focus:outline-none ${
              spinning ? 'otp-box-spinning' : ''
            } ${
              isComplete && celebrateOnComplete
                ? 'border-emerald-700 text-emerald-700 shadow-[0_0_16px_-2px_rgba(57,255,136,0.45)]'
                : 'border-ink-200'
            } focus:border-emerald-700 focus:shadow-[0_0_0_3px_rgba(57,255,136,0.18)]`}
          />
        );
      })}
    </div>
  );
}
