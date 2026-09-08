import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus, ArrowRight } from 'lucide-react';
import { ParentShell } from '../components/ParentShell';
import { Button } from '../components/ui/Button';
import { PayWithMpesa } from '../components/PayWithMpesa';
import { DownloadStatementLink } from '../components/DownloadStatementLink';
import { PaymentProgressBar } from '../components/PaymentProgressBar';
import { RecentActivityFeed } from '../components/RecentActivityFeed';
import { useMyChildren } from '../hooks/useMyChildren';
import { useAuthStore } from '../store/authStore';
import { getMyProfile } from '../api/user';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

export function ParentDashboardPage() {
  const navigate = useNavigate();
  const { children, loading, error, refetch } = useMyChildren();
  const user = useAuthStore((s) => s.user);
  const [phone, setPhone] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    getMyProfile().then((profile) => setPhone(profile.phone)).catch(() => {});
  }, []);

  // After initiating an M-Pesa payment, the parent needs to see their
  // balance update once they enter their PIN on their phone — that
  // confirmation arrives asynchronously via Safaricom's callback, so we
  // poll for a short window rather than expecting an instant update.
  function handlePaymentInitiated() {
    setPolling(true);
    let attempts = 0;
    const interval = setInterval(() => {
      attempts++;
      refetch();
      if (attempts >= 10) {
        clearInterval(interval);
        setPolling(false);
      }
    }, 4000);
  }

  const familyTotalDue = children.reduce((sum, c) => sum + Number(c.balance_due), 0);

  // The single most time-sensitive thing a parent needs to see: whichever
  // unpaid invoice is due soonest across ALL their children, not just the
  // first child in the list.
  const upcoming = children
    .flatMap((child) =>
      child.invoices
        .filter((inv) => inv.status !== 'PAID' && inv.status !== 'CANCELLED')
        .map((inv) => ({ child, invoice: inv }))
    )
    .sort((a, b) => new Date(a.invoice.due_date).getTime() - new Date(b.invoice.due_date).getTime())[0];

  return (
    <ParentShell>
      <div className="flex items-start justify-between gap-4 mb-1">
        <h1 className="font-display text-2xl text-ink-900 font-medium">
          Welcome{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}
        </h1>
        <button
          onClick={() => navigate('/verify-child')}
          className="shrink-0 flex items-center gap-1.5 text-sm font-medium text-ink-900 hover:underline underline-offset-2"
        >
          <UserPlus className="w-4 h-4" strokeWidth={2} />
          Link another child
        </button>
      </div>
      <p className="text-sm text-ink-600 mb-6">Here's the fee status across your family.</p>

      {error && (
        <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
          {error}
        </div>
      )}

      {polling && (
        <div role="status" className="bg-ink-100 text-ink-700 rounded-md px-4 py-3 text-sm mb-6">
          Waiting for payment confirmation from M-Pesa — this updates automatically.
        </div>
      )}

      {loading ? (
        <p className="text-sm text-ink-600">Loading…</p>
      ) : children.length === 0 ? (
        <div className="bg-white border border-ink-200 rounded-lg px-6 py-12 text-center">
          <p className="text-sm text-ink-900 font-medium">No children linked to your account yet</p>
          <p className="text-xs text-ink-600 mt-1 mb-4">
            Enter your child's admission number to send a link request to the school office.
          </p>
          <Button onClick={() => navigate('/verify-child')} className="inline-flex items-center gap-2">
            <UserPlus className="w-4 h-4" /> Link a child
          </Button>
        </div>
      ) : (
        <>
          {children.length > 1 && (
            <div className="bg-white border border-ink-200 rounded-lg px-5 py-4 mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-ink-600">Combined balance — {children.length} children</p>
                <p className={`figure text-2xl font-medium ${familyTotalDue > 0 ? 'text-clay-700' : 'text-emerald-700'}`}>
                  {formatCurrency(familyTotalDue)}
                </p>
              </div>
            </div>
          )}

          {upcoming && (
            <div className="bg-amber-100/40 border border-ink-200 rounded-lg px-5 py-4 mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-xs text-ink-700">
                  Next payment due — {upcoming.child.full_name}, {new Date(upcoming.invoice.due_date).toLocaleDateString('en-KE')}
                </p>
                <p className="figure text-lg font-medium text-ink-900">
                  {formatCurrency(Number(upcoming.invoice.total_amount) - Number(upcoming.invoice.amount_paid))}
                </p>
              </div>
              <PayWithMpesa invoiceId={upcoming.invoice.id} defaultPhone={phone} onInitiated={handlePaymentInitiated} />
            </div>
          )}

          <div className="mb-6">
            <RecentActivityFeed children={children} />
          </div>

          <div className="flex flex-col gap-3">
            {children.map((child) => {
              const balance = Number(child.balance_due);
              const totalDue = child.invoices.reduce((sum, inv) => sum + Number(inv.total_amount), 0);
              const totalPaid = child.invoices.reduce((sum, inv) => sum + Number(inv.amount_paid), 0);
              return (
                <div key={child.id} className="bg-white border border-ink-200 rounded-lg overflow-hidden">
                  <div className="px-5 py-4 flex items-start justify-between">
                    <div>
                      <h2 className="font-display text-lg text-ink-900 font-medium">{child.full_name}</h2>
                      <p className="text-xs text-ink-600 mt-0.5">
                        {child.class_name || 'Class not assigned'} · {child.admission_number}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-ink-600">Balance due</p>
                      <p className={`figure text-xl font-medium ${balance > 0 ? 'text-clay-700' : 'text-emerald-700'}`}>
                        {formatCurrency(balance)}
                      </p>
                    </div>
                  </div>

                  {child.invoices.length > 0 && (
                    <div className="px-5">
                      <PaymentProgressBar totalDue={totalDue} totalPaid={totalPaid} />
                    </div>
                  )}

                  <div className="px-5 py-3 mt-2 border-t border-ink-200 flex items-center justify-between">
                    <DownloadStatementLink studentId={child.id} />
                    <button
                      onClick={() => navigate(`/parent/invoices?child=${child.id}`)}
                      className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
                    >
                      View invoices <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </ParentShell>
  );
}
