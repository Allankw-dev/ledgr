import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Wallet } from 'lucide-react';
import { DxCard } from './DxCard';
import { formatCurrency } from './format';

export interface DonutSegment {
  name: string;
  value: number;
  color: string;
}

interface Props {
  title: string;
  segments: DonutSegment[];
  centerValue: string;
  centerLabel: string;
  headlineLabel: string;
  headlineValue: string;
}

export function DonutCard({ title, segments, centerValue, centerLabel, headlineLabel, headlineValue }: Props) {
  const live = segments.filter((s) => s.value > 0);
  const hasData = live.length > 0;
  const data = hasData ? live : [{ name: 'Nothing yet', value: 1, color: 'rgba(255,255,255,0.08)' }];

  return (
    <DxCard className="@container h-full flex flex-col p-5 sm:p-6">
      <h2 className="font-display text-lg text-ink-900 mb-5">{title}</h2>
      <div className="flex-1 flex flex-col justify-center @lg:flex-row @lg:items-center gap-6 @lg:gap-8">
        <div className="relative w-[168px] h-[168px] shrink-0 mx-auto @lg:mx-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius="72%"
                outerRadius="100%"
                paddingAngle={hasData && live.length > 1 ? 2 : 0}
                cornerRadius={4}
                startAngle={90}
                endAngle={-270}
                stroke="none"
              >
                {data.map((d) => (
                  <Cell key={d.name} fill={d.color} />
                ))}
              </Pie>
              {hasData && (
                <Tooltip
                  formatter={(v) => formatCurrency(Number(v))}
                  contentStyle={{ borderRadius: 10, background: '#1C1F23', border: '1px solid rgba(255,255,255,0.08)', fontSize: 12 }}
                  itemStyle={{ color: '#F3F4FA' }}
                />
              )}
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="figure text-2xl text-ink-900">{centerValue}</span>
            <span className="text-xs text-ink-600 mt-0.5">{centerLabel}</span>
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-5">
            <span className="w-10 h-10 rounded-lg bg-lime/15 text-lime flex items-center justify-center shrink-0">
              <Wallet className="w-5 h-5" strokeWidth={1.75} />
            </span>
            <div className="min-w-0">
              <p className="text-xs text-ink-600">{headlineLabel}</p>
              <p className="figure text-xl text-ink-900 truncate">{headlineValue}</p>
            </div>
          </div>
          {hasData ? (
            <ul className="flex flex-col gap-3">
              {live.map((s) => (
                <li key={s.name} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2 min-w-0 text-ink-600">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: s.color }} />
                    <span className="truncate">{s.name}</span>
                  </span>
                  <span className="figure text-ink-900 shrink-0">{formatCurrency(s.value)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-600">Payments will show up here as they come in.</p>
          )}
        </div>
      </div>
    </DxCard>
  );
}
