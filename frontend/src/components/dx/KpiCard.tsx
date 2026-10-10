import { TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { AnimatedAmount } from '../AnimatedAmount';
import { DxCard } from './DxCard';

interface KpiCardProps {
  label: string;
  /** Undefined while loading. */
  value?: number;
  format: (n: number) => string;
  /** e.g. "+12% vs last term" — the first word is coloured, the rest is dim. */
  trend?: string;
  direction?: 'up' | 'down' | 'neutral';
  className?: string;
}

export function KpiCard({ label, value, format, trend, direction = 'neutral', className = '' }: KpiCardProps) {
  const [lead, ...rest] = (trend ?? '').split(' ');
  const tone = direction === 'up' ? 'text-green' : direction === 'down' ? 'text-coral' : 'text-ink-600';
  const Icon = direction === 'up' ? TrendingUp : direction === 'down' ? TrendingDown : Minus;

  return (
    <DxCard className={`p-4 sm:p-5 flex flex-col justify-between gap-4 min-h-[128px] sm:min-h-[136px] ${className}`}>
      <p className="text-sm text-ink-600">{label}</p>
      <p className="figure text-[1.1rem] sm:text-[1.4rem] leading-tight text-ink-900 whitespace-nowrap">
        {value === undefined ? '—' : <AnimatedAmount value={value} format={format} />}
      </p>
      {trend ? (
        <p className="flex items-center gap-1 sm:gap-1.5 text-[11px] sm:text-xs">
          <Icon className={`w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0 ${tone}`} strokeWidth={2.25} />
          <span className={`font-medium ${tone}`}>{lead}</span>
          <span className="text-ink-400 truncate">{rest.join(' ')}</span>
        </p>
      ) : (
        <span className="h-4" aria-hidden="true" />
      )}
    </DxCard>
  );
}
