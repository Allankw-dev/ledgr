import { DxCard } from './DxCard';

const R = 52;
const ARC = 'M8 60 A52 52 0 0 1 112 60';
const LEN = Math.PI * R;

function clampPercent(p: number) {
  if (!Number.isFinite(p)) return 0;
  return Math.max(0, Math.min(100, Math.round(p)));
}

export function GaugeCard({ label, percent, note, loading, className = '' }: { label: string; percent: number; note?: string; loading?: boolean; className?: string }) {
  const pct = clampPercent(percent);
  return (
    <DxCard className={`relative overflow-hidden p-4 sm:p-5 min-h-[128px] sm:min-h-[136px] ${className}`}>
      <p className="text-sm text-ink-600">{label}</p>
      <p className="figure text-[1.4rem] sm:text-[1.75rem] leading-none text-ink-900 mt-5">{loading ? '—' : `${pct}%`}</p>
      {note && <p className="text-xs text-ink-400 mt-2 truncate sm:max-w-[55%]">{note}</p>}
      <svg viewBox="0 0 120 66" className="absolute right-3 bottom-3 w-[64px] sm:w-[104px] h-auto" role="img" aria-label={`${pct}% collected`}>
        <defs>
          <linearGradient id="dxGaugeGrad" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#3F7A12" />
            <stop offset="100%" stopColor="#B8F24B" />
          </linearGradient>
        </defs>
        <path d={ARC} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" strokeLinecap="round" />
        <path
          d={ARC}
          fill="none"
          stroke="url(#dxGaugeGrad)"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={LEN}
          strokeDashoffset={LEN * (1 - (loading ? 0 : pct) / 100)}
          style={{ transition: 'stroke-dashoffset 0.9s cubic-bezier(0.16, 1, 0.3, 1)' }}
        />
      </svg>
    </DxCard>
  );
}
