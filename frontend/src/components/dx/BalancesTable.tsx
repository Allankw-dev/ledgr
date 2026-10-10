import { Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import type { TopRiskInvoice } from '../../hooks/useDashboardAnalytics';
import { Avatar } from './Avatar';
import { DxCard } from './DxCard';
import { formatCurrency } from './format';

const LEVEL: Record<TopRiskInvoice['risk_level'], string> = {
  low: 'bg-green-100 text-green',
  medium: 'bg-amber-100 text-amber',
  high: 'bg-coral-100 text-coral',
};

export function BalancesTable({ rows }: { rows: TopRiskInvoice[] }) {
  return (
    <DxCard className="overflow-hidden">
      <div className="flex items-center justify-between px-5 sm:px-6 pt-5 pb-3">
        <h2 className="font-display text-lg text-ink-900">Highest-risk balances</h2>
        <Link to="/invoices" className="text-xs text-ink-600 hover:text-lime transition-colors">
          All invoices
        </Link>
      </div>
      {rows.length === 0 ? (
        <p className="px-5 sm:px-6 pb-6 text-sm text-ink-600">No high-risk unpaid invoices right now.</p>
      ) : (
        <>
          <div className="hidden sm:grid grid-cols-[1fr_72px_130px] gap-3 px-6 py-2 border-y border-white/[0.06] text-xs text-ink-400">
            <span>Student</span>
            <span className="text-center">Risk</span>
            <span className="text-right">Balance</span>
          </div>
          <ul className="divide-y divide-white/[0.05]">
            {rows.map((r) => (
              <li key={r.invoice_id} className="grid grid-cols-[1fr_auto] sm:grid-cols-[1fr_72px_130px] items-center gap-3 px-5 sm:px-6 py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <Avatar name={r.student_name} size={36} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink-900 truncate">{r.student_name}</p>
                    <p className="text-xs text-ink-400 truncate">{r.class_name}</p>
                  </div>
                </div>
                <span className={`hidden sm:inline-flex items-center justify-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${LEVEL[r.risk_level]}`}>
                  {r.risk_level === 'high' && <AlertTriangle className="w-3 h-3" />}
                  {Math.round(r.risk_score)}
                </span>
                <span className="figure text-sm text-ink-900 text-right">{formatCurrency(Number(r.balance))}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </DxCard>
  );
}
