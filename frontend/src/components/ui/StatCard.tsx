import type { ReactNode, CSSProperties } from 'react';
import { AnimatedAmount } from '../AnimatedAmount';

interface StatCardProps {
  label: string;
  value: string;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'neutral';
  icon: ReactNode;
  /** The one hero metric per screen — gets the green glow border, the
     raised neumorphic surface, and a green value, so it reads as "the
     number that matters most" rather than every card competing for
     attention. */
  highlight?: boolean;
  /** Position in a stat row — staggers this card's entrance a beat after
     the one before it, so a dashboard's numbers settle in as one
     choreographed sequence on load rather than everything (or nothing)
     animating at once. Omit outside of a stat grid. */
  index?: number;
  /** Optional numeric form of `value` — when given, the figure counts up on load. */
  amount?: number;
  format?: (n: number) => string;
}

const trendColor = {
  up: 'text-emerald-700',
  down: 'text-clay-700',
  neutral: 'text-ink-600',
};

export function StatCard({ label, value, trend, trendDirection = 'neutral', icon, highlight = false, index, amount, format }: StatCardProps) {
  const staggered = index !== undefined;
  return (
    <div
      className={`bg-panel border rounded-xl p-5 transition-transform duration-300 hover:-translate-y-0.5 ${staggered ? 'reveal' : ''} ${
        highlight ? 'sheen neu-surface border-emerald-700/35 shadow-[0_0_30px_-8px_rgba(57,255,136,0.35)]' : 'border-ink-200'
      }`}
      style={staggered ? ({ '--reveal-delay': `${index * 0.06}s` } as CSSProperties) : undefined}
    >
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm text-ink-600 font-medium">{label}</p>
        <div className={`w-9 h-9 -mt-1 -mr-1 rounded-xl flex items-center justify-center ${highlight ? 'bg-emerald-100 text-emerald-700' : 'bg-ink-100 text-ink-600'}`}>{icon}</div>
      </div>
      <p
        className={`figure text-2xl font-medium ${highlight ? 'text-emerald-700' : 'text-ink-900'} ${!staggered && highlight ? 'reveal' : ''}`}
        style={!staggered && highlight ? ({ '--reveal-delay': '0.15s' } as CSSProperties) : undefined}
      >
        {amount !== undefined && format ? <AnimatedAmount value={amount} format={format} /> : value}
      </p>
      {trend && <p className={`text-xs font-medium mt-1.5 ${trendColor[trendDirection]}`}>{trend}</p>}
    </div>
  );
}
