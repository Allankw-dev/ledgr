import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: string;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'neutral';
  icon: ReactNode;
}

const trendColor = {
  up: 'text-emerald-700',
  down: 'text-clay-700',
  neutral: 'text-ink-600',
};

export function StatCard({ label, value, trend, trendDirection = 'neutral', icon }: StatCardProps) {
  return (
    <div className="bg-white border border-ink-200 rounded-lg p-5">
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm text-ink-600 font-medium">{label}</p>
        <div className="text-ink-400">{icon}</div>
      </div>
      <p className="figure text-2xl font-medium text-ink-900">{value}</p>
      {trend && <p className={`text-xs font-medium mt-1.5 ${trendColor[trendDirection]}`}>{trend}</p>}
    </div>
  );
}
