import { Wallet, AlertCircle, Users, Receipt, ShieldAlert } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { StatCard } from '../components/ui/StatCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useDashboardData } from '../hooks/useDashboardData';
import { useAnomalies } from '../hooks/useAnomalies';
import { useAuthStore } from '../store/authStore';

function formatCurrency(amount: number, currency = 'KES') {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
}

export function DashboardPage() {
  const { invoices, students, loading, error } = useDashboardData();
  const { anomalies } = useAnomalies();
  const user = useAuthStore((s) => s.user);

  const totalCollected = invoices.reduce((sum, inv) => sum + Number(inv.amount_paid), 0);
  const totalOutstanding = invoices.reduce(
    (sum, inv) => sum + (Number(inv.total_amount) - Number(inv.amount_paid)),
    0
  );
  const overdueCount = invoices.filter((inv) => inv.status === 'OVERDUE').length;

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="mb-8">
          <h1 className="font-display text-2xl text-ink-900 font-medium">
            Good day{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}
          </h1>
          <p className="text-sm text-ink-600 mt-1">Here's where your school's fee collection stands.</p>
        </div>

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Collected this term"
            value={loading ? '—' : formatCurrency(totalCollected)}
            icon={<Wallet className="w-5 h-5" strokeWidth={1.75} />}
          />
          <StatCard
            label="Outstanding balance"
            value={loading ? '—' : formatCurrency(totalOutstanding)}
            trend={!loading && totalOutstanding > 0 ? 'Needs follow-up' : undefined}
            trendDirection="down"
            icon={<Receipt className="w-5 h-5" strokeWidth={1.75} />}
          />
          <StatCard
            label="Overdue invoices"
            value={loading ? '—' : String(overdueCount)}
            trend={!loading && overdueCount > 0 ? 'Review and remind' : 'All on track'}
            trendDirection={overdueCount > 0 ? 'down' : 'up'}
            icon={<AlertCircle className="w-5 h-5" strokeWidth={1.75} />}
          />
          <StatCard
            label="Active students"
            value={loading ? '—' : String(students.length)}
            icon={<Users className="w-5 h-5" strokeWidth={1.75} />}
          />
        </div>

        {anomalies.length > 0 && (
          <div className="bg-white border border-clay-600/30 rounded-lg overflow-hidden mb-8">
            <div className="px-5 py-4 border-b border-ink-200 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-clay-700" strokeWidth={2} />
              <h2 className="font-display text-base text-ink-900 font-medium">
                Flagged payments <span className="text-ink-400 font-normal text-sm">({anomalies.length})</span>
              </h2>
            </div>
            <div className="divide-y divide-ink-100">
              {anomalies.slice(0, 5).map((a) => (
                <div key={a.payment_id} className="px-5 py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="figure text-sm font-medium text-ink-900">
                      {formatCurrency(Number(a.amount))}
                    </span>
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        a.severity === 'high' ? 'bg-clay-100 text-clay-700' : 'bg-amber-100 text-amber-700'
                      }`}
                    >
                      {a.severity === 'high' ? 'Review recommended' : 'Worth a look'}
                    </span>
                  </div>
                  {a.reasons.map((reason, i) => (
                    <p key={i} className="text-xs text-ink-600">
                      {reason}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
          <div className="px-5 py-4 border-b border-ink-200">
            <h2 className="font-display text-base text-ink-900 font-medium">Recent invoices</h2>
          </div>

          {loading ? (
            <div className="px-5 py-12 text-center text-sm text-ink-600">Loading invoices…</div>
          ) : invoices.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="text-sm text-ink-600">No invoices yet.</p>
              <p className="text-xs text-ink-400 mt-1">
                Generate invoices for a term to start tracking payments.
              </p>
            </div>
          ) : (
            <div className="ledger-lines">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-ink-600">
                    <th className="px-5 py-2 font-medium">Invoice</th>
                    <th className="px-5 py-2 font-medium">Due date</th>
                    <th className="px-5 py-2 font-medium text-right">Total</th>
                    <th className="px-5 py-2 font-medium text-right">Paid</th>
                    <th className="px-5 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.slice(0, 10).map((inv) => (
                    <tr key={inv.id} className="h-9 text-ink-900">
                      <td className="px-5 figure text-xs text-ink-600">{inv.id.slice(0, 8)}</td>
                      <td className="px-5">{new Date(inv.due_date).toLocaleDateString('en-KE')}</td>
                      <td className="px-5 figure text-right">{formatCurrency(Number(inv.total_amount))}</td>
                      <td className="px-5 figure text-right">{formatCurrency(Number(inv.amount_paid))}</td>
                      <td className="px-5">
                        <StatusBadge status={inv.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
