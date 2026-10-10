import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts';
import { DxCard } from './DxCard';
import { formatCurrency } from './format';

export interface TrendPoint {
  name: string;
  paid: number;
}

export function AreaTrendCard({ title, headline, subtitle, points }: { title: string; headline: string; subtitle: string; points: TrendPoint[] }) {
  return (
    <DxCard className="p-5 col-span-2 overflow-hidden">
      <p className="text-sm text-ink-600">{title}</p>
      <p className="figure text-xl text-ink-900 mt-1">{headline}</p>
      <p className="text-[11px] text-ink-400 mt-0.5">{subtitle}</p>
      {points.length >= 2 ? (
        <div className="h-28 -mx-5 -mb-5 mt-3">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="dxAreaFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#39FF88" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#39FF88" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Tooltip
                formatter={(v) => formatCurrency(Number(v))}
                labelStyle={{ color: '#8891B0' }}
                itemStyle={{ color: '#F3F4FA' }}
                contentStyle={{ borderRadius: 10, background: '#1C1F23', border: '1px solid rgba(255,255,255,0.08)', fontSize: 12 }}
                cursor={{ stroke: 'rgba(255,255,255,0.15)' }}
              />
              <Area
                type="monotone"
                dataKey="paid"
                name="Collected"
                stroke="#39FF88"
                strokeWidth={2}
                fill="url(#dxAreaFill)"
                dot={false}
                activeDot={{ r: 4, fill: '#39FF88', stroke: '#0B1203', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-xs text-ink-400 mt-6 mb-1">The trend appears once you have two terms of payments.</p>
      )}
    </DxCard>
  );
}
