import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import type { HealthSeverity, SchoolPaymentsHealth } from '../api/subscription';
import { DxCard } from './dx/DxCard';
import { money } from '../lib/money';

const BADGE: Record<HealthSeverity, string> = {
  bad: 'bg-coral-100 text-coral',
  warn: 'bg-amber-100 text-amber',
  info: 'bg-white/[0.06] text-ink-600',
  ok: 'bg-green-100 text-green',
};
const LABEL: Record<HealthSeverity, string> = { bad: 'Broken', warn: 'Needs a look', info: 'Note', ok: 'Healthy' };

const ago = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('en-KE', { day: 'numeric', month: 'short' }) : 'never');

/**
 * Every school's online payments on one screen, worst first, so a broken paybill is found by the operator and not by an
 * angry bursar. Counts only. Tapping a school filters the list below to it.
 */
export function PaymentsHealthPanel({
  rows,
  error,
  onRefresh,
  onOpenSchool,
}: {
  rows: SchoolPaymentsHealth[] | null;
  error: string;
  onRefresh: () => void;
  onOpenSchool: (name: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);

  if (error) {
    return (
      <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm flex items-center justify-between">
        {error}
        <button onClick={onRefresh} className="underline">Try again</button>
      </div>
    );
  }
  if (!rows) return <p className="text-sm text-ink-600">Checking payments…</p>;
  if (rows.length === 0) return null;

  const bad = rows.filter((r) => r.severity === 'bad').length;
  const warn = rows.filter((r) => r.severity === 'warn').length;
  const live = rows.filter((r) => r.mpesa_mode !== 'OFF').length;
  const flagged = rows.filter((r) => r.severity === 'bad' || r.severity === 'warn');
  const shown = showAll ? rows : flagged;
  const allGood = flagged.length === 0;

  return (
    <DxCard className="p-5" >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg text-ink-900">Payments health</h2>
          <p className="text-xs text-ink-400 mt-1">
            {live} of {rows.length} school{rows.length === 1 ? '' : 's'} take online M-Pesa.{' '}
            {allGood ? 'Nothing needs your attention.' : `${bad ? `${bad} broken, ` : ''}${warn} need${warn === 1 ? 's' : ''} a look.`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded-full border border-white/[0.1] px-3 py-1.5 text-xs text-ink-900 hover:border-lime/50 transition-colors"
            onClick={() => setShowAll((v) => !v)}
            aria-pressed={showAll}
          >
            {showAll ? 'Only show problems' : 'Show every school'}
          </button>
          <button
            className="rounded-full border border-white/[0.1] p-2 text-ink-900 hover:border-lime/50 transition-colors"
            onClick={onRefresh}
            aria-label="Refresh payments health"
          >
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>

      {shown.length > 0 && (
        <ul className="mt-4 divide-y divide-white/[0.06]">
          {shown.map((r) => (
            <li key={r.school_id} className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button className="text-sm text-ink-900 font-medium hover:underline text-left" onClick={() => onOpenSchool(r.school_name)}>
                  {r.school_name}
                </button>
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${BADGE[r.severity]}`}>{LABEL[r.severity]}</span>
              </div>
              <p className="mt-1 text-xs text-ink-400">
                {r.mpesa_mode === 'OFF' ? 'M-Pesa off' : r.mpesa_mode === 'OWN' ? `Own paybill ${r.shortcode ?? ''}` : 'Server-wide paybill'}
                {r.mpesa_mode !== 'OFF' && (
                  <>
                    {' · '}last payment {ago(r.last_confirmed_at)}
                    {' · '}
                    {r.confirmed_30d_count} in 30 days ({money(r.confirmed_30d_amount, r.currency)})
                  </>
                )}
              </p>
              {r.attention.length > 0 && (
                <ul className="mt-1.5 list-disc pl-5 text-xs text-ink-900 flex flex-col gap-0.5">
                  {r.attention.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </DxCard>
  );
}
