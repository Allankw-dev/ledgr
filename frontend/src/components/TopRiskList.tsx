import { AlertTriangle } from 'lucide-react';
import type { TopRiskInvoice } from '../hooks/useDashboardAnalytics';

function formatCurrency(amount: number, currency = 'KES') {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
}

const levelStyles: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-clay-100 text-clay-700',
};

export function TopRiskList({ invoices }: { invoices: TopRiskInvoice[] }) {
  if (invoices.length === 0) {
    return <p className="text-sm text-ink-600">No high-risk unpaid invoices right now.</p>;
  }

  return (
    <div className="divide-y divide-ink-100">
      {invoices.map((r) => (
        <div key={r.invoice_id} className="py-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm text-ink-900 font-medium truncate">{r.student_name}</p>
            <p className="text-xs text-ink-600">{r.class_name}</p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="figure text-sm text-ink-900">{formatCurrency(Number(r.balance))}</span>
            <span
              className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${levelStyles[r.risk_level]}`}
            >
              {r.risk_level === 'high' && <AlertTriangle className="w-3 h-3" />}
              {Math.round(r.risk_score)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
