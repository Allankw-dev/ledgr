import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TermCollectionPoint } from '../hooks/useDashboardAnalytics';

function formatCurrency(amount: number, currency = 'KES') {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
}

function formatCompact(amount: number) {
  return new Intl.NumberFormat('en-KE', { notation: 'compact', maximumFractionDigits: 1 }).format(amount);
}

export function CollectionChart({ points }: { points: TermCollectionPoint[] }) {
  const data = points.map((p) => ({
    name: p.term_name,
    billed: Number(p.total_billed),
    paid: Number(p.total_paid),
  }));

  if (data.length === 0) {
    return <p className="text-sm text-ink-600">No terms with invoices yet.</p>;
  }

  return (
    <div className="h-64 -ml-2">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E4E2DA" />
          <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#3D5280' }} axisLine={{ stroke: '#E4E2DA' }} tickLine={false} />
          <YAxis
            tickFormatter={formatCompact}
            tick={{ fontSize: 12, fill: '#3D5280' }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip
            formatter={(value: number) => formatCurrency(value)}
            contentStyle={{ borderRadius: 8, borderColor: '#E4E2DA', fontSize: 13 }}
          />
          <Bar dataKey="billed" name="Billed" fill="#D9D6CB" radius={[4, 4, 0, 0]} />
          <Bar dataKey="paid" name="Paid" fill="#16213D" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
