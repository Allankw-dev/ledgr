import { useEffect, useState } from 'react';
import { getMpesaStatus } from '../api/mpesa';
import { useAuthStore } from '../store/authStore';

// One request per school per page load, shared by every pay button on the screen (an invoice list can have a dozen).
// Keyed by school so a different account signing in on the same page never sees the previous school's answer.
const answers = new Map<string, Promise<boolean | null>>();

/** For tests, and after a payment-settings change. */
export function resetMpesaAvailability() {
  answers.clear();
}

function load(schoolId: string): Promise<boolean | null> {
  let answer = answers.get(schoolId);
  if (!answer) {
    // Can't tell (network blip, server error) => null, which shows the button. The server refuses a payment it can't
    // take with a clear message, so hiding the button on a hiccup would be the worse mistake.
    answer = getMpesaStatus().then((s) => s.enabled).catch(() => null);
    answers.set(schoolId, answer);
  }
  return answer;
}

/**
 * true  - online M-Pesa works for this school
 * false - it is switched off / not set up, so DON'T offer a button that can only fail
 * null  - not known yet (still loading, or the check failed): treat as available
 */
export function useMpesaAvailable(): boolean | null {
  const schoolId = useAuthStore((s) => s.user?.school_id) ?? '';
  const [available, setAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!schoolId) return;
    void load(schoolId).then((value) => {
      if (!cancelled) setAvailable(value);
    });
    return () => {
      cancelled = true;
    };
  }, [schoolId]);

  return available;
}
