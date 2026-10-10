import { CheckCircle2 } from 'lucide-react';
import type { ParentStudentView } from '../types';
import { RailSection } from './dx/RightRail';

interface ActivityRow {
  id: string;
  childName: string;
  amount: number;
  method: string;
  paidAt: string;
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

function formatMethod(method: string) {
  // Backend sends enum values like "MPESA" / "CASH" / "BANK_TRANSFER".
  return method.replace(/_/g, ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase());
}

/**
 * Flattens payments out of every child's every invoice into one
 * chronological feed. Confirmed payments only (that's all the backend
 * ever sends here — see parent.py), so every row is a real receipt, not a
 * pending or failed attempt.
 */
function buildActivity(children: ParentStudentView[], limit: number): ActivityRow[] {
  const rows: ActivityRow[] = [];
  for (const child of children) {
    for (const invoice of child.invoices) {
      for (const payment of invoice.payments) {
        if (!payment.paid_at) continue;
        rows.push({
          id: payment.id,
          childName: child.full_name,
          amount: Number(payment.amount),
          method: payment.method,
          paidAt: payment.paid_at,
        });
      }
    }
  }
  rows.sort((a, b) => new Date(b.paidAt).getTime() - new Date(a.paidAt).getTime());
  return rows.slice(0, limit);
}

export function RecentActivityFeed({ children, limit = 6, variant = 'card' }: { children: ParentStudentView[]; limit?: number; variant?: 'card' | 'rail' }) {
  const activity = buildActivity(children, limit);
  const showChildName = children.length > 1;

  if (variant === 'rail') {
    return (
      <RailSection title="Recent payments">
        {activity.length === 0 ? (
          <p className="text-sm text-ink-600">No payments yet. They'll show up here once confirmed.</p>
        ) : (
          <ol className="flex flex-col gap-3">
            {activity.map((row) => (
              <li key={row.id} className="flex items-center gap-3">
                <span className="w-9 h-9 rounded-full bg-green-100 text-green flex items-center justify-center shrink-0">
                  <CheckCircle2 className="w-4 h-4" strokeWidth={2} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink-900 leading-snug">Payment confirmed{showChildName ? ` for ${row.childName}` : ''}</p>
                  <p className="text-xs text-ink-400 mt-0.5">
                    {formatMethod(row.method)} · {new Date(row.paidAt).toLocaleDateString('en-KE', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <p className="figure text-sm text-ink-900 shrink-0">{formatCurrency(row.amount)}</p>
              </li>
            ))}
          </ol>
        )}
      </RailSection>
    );
  }

  if (activity.length === 0) {
    return (
      <div className="bg-panel border border-ink-200 rounded-lg px-6 py-8 text-center">
        <p className="text-sm text-ink-600">No activity yet — payments will show up here once confirmed.</p>
      </div>
    );
  }

  return (
    <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden">
      <div className="px-5 py-4 border-b border-ink-200">
        <h2 className="font-display text-base text-ink-900 font-medium">Recent activity</h2>
      </div>
      <ul>
        {activity.map((row) => (
          <li key={row.id} className="px-5 py-3 border-b border-ink-100 last:border-b-0 flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" strokeWidth={2} />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-ink-900">
                Payment confirmed{showChildName ? ` for ${row.childName}` : ''}
              </p>
              <p className="text-xs text-ink-500 mt-0.5">
                {formatMethod(row.method)} · {new Date(row.paidAt).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' })}
              </p>
            </div>
            <p className="figure text-sm font-medium text-ink-900 shrink-0">{formatCurrency(row.amount)}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
