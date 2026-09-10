import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: string;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'neutral';
  icon: ReactNode;
  /** The one hero metric per screen — gets the green glow border and a
     green value, so it reads as "the number that matters most" rather
     than every card competing for attention. */
  highlight?: boolean;
}

const trendColor = {
  up: 'text-emerald-700',
  down: 'text-clay-700',
  neutral: 'text-ink-600',
};

export function StatCard({ label, value, trend, trendDirection = 'neutral', icon, highlight = false }: StatCardProps) {
  return (
    <div
      className={`bg-panel border rounded-lg p-5 ${
        highlight ? 'border-emerald-700/35 shadow-[0_0_30px_-8px_rgba(57,255,136,0.35)]' : 'border-ink-200'
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm text-ink-600 font-medium">{label}</p>
        <div className="text-ink-400">{icon}</div>
      </div>
      <p className={`figure text-2xl font-medium ${highlight ? 'text-emerald-700' : 'text-ink-900'}`}>{value}</p>
      {trend && <p className={`text-xs font-medium mt-1.5 ${trendColor[trendDirection]}`}>{trend}</p>}
    </div>
  );
}
